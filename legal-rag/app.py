"""Streamlit UI for the Legal RAG pipeline.

This is a thin HTTP client over the FastAPI backend (src/api/main.py) - it
holds no pipeline state and imports nothing from src/ except environment
loading. The backend owns the embedding model, vector store, and LLM client;
running the pipeline in two processes (this one included) would mean two
writers on the same Chroma SQLite file, so all ingestion, retrieval, and
generation happen via HTTP calls to the API.

Start the API first: uvicorn src.api.main:app
Then: streamlit run app.py
"""

from __future__ import annotations

import os
from pathlib import Path

import httpx
import streamlit as st
from dotenv import load_dotenv

APP_DIR = Path(__file__).resolve().parent
load_dotenv(APP_DIR / ".env")

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
DEFAULT_QUESTION = "What are the termination conditions?"
REQUEST_TIMEOUT_SECONDS = 60.0


def initialize_state() -> None:
    st.session_state.setdefault("question", DEFAULT_QUESTION)
    st.session_state.setdefault("last_answer", None)
    st.session_state.setdefault("refused", False)
    st.session_state.setdefault("citations", [])
    st.session_state.setdefault("upload_message", None)
    st.session_state.setdefault("trace_data", None)


def check_api_health() -> dict | None:
    try:
        response = httpx.get(f"{API_BASE_URL}/health", timeout=5.0)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError:
        return None


def process_upload(uploaded_file, category: str) -> None:
    if uploaded_file is None:
        st.session_state.upload_message = "Select a PDF before processing."
        return

    files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")}
    data = {"category": category.strip() or "general"}

    try:
        response = httpx.post(f"{API_BASE_URL}/ingest", files=files, data=data, timeout=REQUEST_TIMEOUT_SECONDS)
    except httpx.HTTPError as exc:
        st.session_state.upload_message = f"Could not reach the API: {exc}"
        return

    if response.status_code >= 400:
        st.session_state.upload_message = response.json().get("detail", response.text)
        return

    result = response.json()
    st.session_state.upload_message = (
        f"Indexed {result['filename']} as '{result['category']}' ({result['chunks_indexed']} chunks)."
    )


def answer_question() -> None:
    try:
        response = httpx.post(
            f"{API_BASE_URL}/query",
            json={"question": st.session_state.question, "top_k": 8},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except httpx.HTTPError as exc:
        st.session_state.last_answer = f"Could not reach the API: {exc}"
        st.session_state.refused = False
        st.session_state.citations = []
        st.session_state.trace_data = None
        return

    if response.status_code >= 400:
        st.session_state.last_answer = response.json().get("detail", response.text)
        st.session_state.refused = False
        st.session_state.citations = []
        st.session_state.trace_data = None
        return

    result = response.json()
    st.session_state.refused = result["refused"]
    st.session_state.last_answer = (
        "No sufficiently relevant sources were found for this question." if result["refused"] else result["answer"]
    )
    st.session_state.citations = result.get("citations", [])
    st.session_state.trace_data = result.get("trace")


def display_trace(trace: dict) -> None:
    with st.expander("RAG Pipeline Trace", expanded=False):
        for step in trace.get("steps", []):
            st.markdown(f"**{step.get('step', 'Unknown')}** - {step.get('status', '')}")

            if "results" in step:
                for res in step["results"][:10]:
                    st.text(
                        f"  [{res['rank']}] {res['document']} (p.{res['page']}, sec {res['section']}) "
                        f"score={res['score']}"
                    )

            if "sources" in step:
                for src in step["sources"]:
                    st.text(f"  SOURCE_{src['rank']} {src['document']} (p.{src['page']}) score={src['score']}")

            if step.get("step") == "3. LLM Generation":
                st.text(
                    f"  model={step.get('model')} citations={step.get('citations_found')} "
                    f"answer_length={step.get('answer_length')}"
                )

        st.markdown("**Raw trace**")
        st.json(trace)


def main() -> None:
    st.set_page_config(page_title="Legal Intelligence Assistant", page_icon="L", layout="wide")
    initialize_state()

    st.title("Legal Intelligence Assistant")
    st.write("Upload a text-based PDF, then ask questions grounded in its contents.")

    health = check_api_health()
    if health is None:
        st.error(f"Cannot reach the API at {API_BASE_URL}. Start it with: uvicorn src.api.main:app")
        return
    st.caption(f"API connected - {health['indexed_chunks']} chunks indexed ({health['embedding_model']})")

    st.subheader("Index a document")
    with st.form("upload_form", clear_on_submit=True):
        uploaded_file = st.file_uploader("PDF document", type=["pdf"])
        upload_category = st.text_input("Category", value="general", help="Examples: contracts, employment, policies")
        process_clicked = st.form_submit_button("Process document", type="primary")
    if process_clicked:
        process_upload(uploaded_file, upload_category)
    st.caption("For bulk ingestion of many PDFs, use scripts/ingest.py instead.")

    if st.session_state.upload_message:
        st.info(st.session_state.upload_message)

    st.divider()
    st.subheader("Ask a question")
    st.text_area("Question", key="question", height=120)
    if st.button("Ask", type="primary"):
        answer_question()

    st.subheader("Answer")
    if st.session_state.refused:
        st.warning(st.session_state.last_answer)
    elif st.session_state.last_answer:
        st.write(st.session_state.last_answer)
    else:
        st.info("Process a document and ask a question to receive a grounded answer.")

    st.subheader("Sources")
    citations = st.session_state.citations
    if citations:
        for citation in citations:
            st.write(f"[{citation['citation_id']}] {citation['document_name']} - Page {citation['page_number']}")
    else:
        st.write("No sources cited yet.")

    st.divider()
    st.subheader("Model Testing & Evaluation")
    st.markdown(
        "Retrieval evaluation runs as a CLI script against a reproducible dataset "
        "(`python scripts/run_evaluation.py`), writing versioned results to "
        "`data/eval_runs/`. See `doc/06-evaluation.md` for the real, measured numbers."
    )

    if st.session_state.trace_data:
        st.divider()
        display_trace(st.session_state.trace_data)


if __name__ == "__main__":
    main()
