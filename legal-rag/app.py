"""Streamlit UI for the Legal RAG pipeline.

This is a thin HTTP client over the FastAPI backend (src/api/main.py) - it
holds no pipeline state and imports nothing from src/ except environment
loading. The backend owns the embedding model, vector store, and LLM client;
running the pipeline in two processes (this one included) would mean two
writers on the same Chroma SQLite file, so all ingestion, retrieval,
generation, and evaluation happen via HTTP calls to the API.

Start the API first: uvicorn src.api.main:app
Then: streamlit run app.py
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import httpx
import streamlit as st
from dotenv import load_dotenv

APP_DIR = Path(__file__).resolve().parent
load_dotenv(APP_DIR / ".env")

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
DEFAULT_QUESTION = "What are the termination conditions?"
REQUEST_TIMEOUT_SECONDS = 60.0
CHUNKING_METHOD_LABELS = {
    "legal": "Legal-aware (structure-based)",
    "recursive": "Recursive character splitter (with overlap)",
    "llm_semantic": "LLM semantic chunking",
}
RETRIEVAL_METHOD_LABELS = {
    "dense": "Dense (embeddings only)",
    "bm25": "BM25 (keyword only)",
    "hybrid": "Hybrid (dense + BM25, RRF)",
    "hybrid_rerank": "Hybrid + reranker",
}


def initialize_state() -> None:
    st.session_state.setdefault("question", DEFAULT_QUESTION)
    st.session_state.setdefault("last_answer", None)
    st.session_state.setdefault("refused", False)
    st.session_state.setdefault("citations", [])
    st.session_state.setdefault("upload_message", None)
    st.session_state.setdefault("trace_data", None)
    st.session_state.setdefault("active_eval_run_id", None)
    st.session_state.setdefault("eval_message", None)
    st.session_state.setdefault("answered_case_id", None)
    st.session_state.setdefault("case_message", None)


def check_api_health() -> dict | None:
    try:
        response = httpx.get(f"{API_BASE_URL}/health", timeout=5.0)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError:
        return None


def process_upload(uploaded_file, category: str, chunking_method: str) -> None:
    if uploaded_file is None:
        st.session_state.upload_message = "Select a PDF before processing."
        return

    files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")}
    data = {"category": category.strip() or "general", "chunking_method": chunking_method}

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
        f"Indexed {result['filename']} as '{result['category']}' "
        f"({result['chunks_indexed']} chunks, {CHUNKING_METHOD_LABELS.get(result['chunking_method'], result['chunking_method'])})."
    )


def answer_question(case_id: str | None) -> None:
    try:
        response = httpx.post(
            f"{API_BASE_URL}/query",
            json={"question": st.session_state.question, "top_k": 8, "case_id": case_id},
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
    if result["refused"] and case_id is not None:
        st.session_state.last_answer = (
            "No sufficiently relevant sources were found for this question within the selected case."
        )
    elif result["refused"]:
        st.session_state.last_answer = "No sufficiently relevant sources were found for this question."
    else:
        st.session_state.last_answer = result["answer"]
    st.session_state.citations = result.get("citations", [])
    st.session_state.trace_data = result.get("trace")
    st.session_state.answered_case_id = result.get("case_id")


def submit_evaluation(retrieval_method: str, chunking_method: str, top_k: int) -> None:
    try:
        response = httpx.post(
            f"{API_BASE_URL}/evaluate",
            json={"retrieval_method": retrieval_method, "chunking_method": chunking_method, "top_k": top_k},
            timeout=10.0,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        st.session_state.eval_message = f"Could not submit evaluation: {exc}"
        return

    result = response.json()
    st.session_state.active_eval_run_id = result["run_id"]
    st.session_state.eval_message = None


def fetch_evaluation_status(run_id: str) -> dict | None:
    try:
        response = httpx.get(f"{API_BASE_URL}/evaluate/{run_id}", timeout=10.0)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError:
        return None


def fetch_evaluation_runs() -> list[dict]:
    try:
        response = httpx.get(f"{API_BASE_URL}/evaluate/runs", timeout=10.0)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError:
        return []


def fetch_documents() -> list[dict]:
    try:
        response = httpx.get(f"{API_BASE_URL}/documents", timeout=10.0)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError:
        return []


def fetch_cases() -> list[dict]:
    try:
        response = httpx.get(f"{API_BASE_URL}/cases", timeout=10.0)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError:
        return []


def create_case(name: str, description: str) -> None:
    if not name.strip():
        st.session_state.case_message = "Case name is required."
        return
    try:
        response = httpx.post(
            f"{API_BASE_URL}/cases",
            json={"name": name.strip(), "description": description.strip() or None},
            timeout=10.0,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        st.session_state.case_message = f"Could not create case: {exc}"
        return
    st.session_state.case_message = f"Created case '{name.strip()}'."


def attach_documents_to_case(case_id: str, document_ids: list[str]) -> None:
    if not document_ids:
        st.session_state.case_message = "Select at least one document to attach."
        return
    try:
        for document_id in document_ids:
            response = httpx.post(
                f"{API_BASE_URL}/cases/{case_id}/documents",
                json={"document_id": document_id},
                timeout=10.0,
            )
            response.raise_for_status()
    except httpx.HTTPError as exc:
        st.session_state.case_message = f"Could not attach document: {exc}"
        return
    st.session_state.case_message = f"Attached {len(document_ids)} document(s) to the case."


def display_trace(trace: dict) -> None:
    with st.expander("RAG Pipeline Trace", expanded=False):
        step_tabs = st.tabs([step.get("step", f"Step {i}") for i, step in enumerate(trace.get("steps", []), start=1)])
        for tab, step in zip(step_tabs, trace.get("steps", [])):
            with tab:
                st.markdown(f"**Status:** {step.get('status', '')}")

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


def render_ingest_tab(health: dict) -> None:
    st.subheader("Index a document")
    with st.form("upload_form", clear_on_submit=True):
        uploaded_file = st.file_uploader("PDF document", type=["pdf"])
        upload_category = st.text_input("Category", value="general", help="Examples: contracts, employment, policies")
        available_methods = health.get("available_chunking_methods", ["legal"])
        chunking_method = st.selectbox(
            "Chunking strategy",
            options=available_methods,
            format_func=lambda m: CHUNKING_METHOD_LABELS.get(m, m),
            help="Each strategy is indexed into its own store. Only the server's default "
            f"strategy ({CHUNKING_METHOD_LABELS.get(health.get('chunking_method', 'legal'))}) "
            "is used to answer questions below - the others are for building comparison indexes.",
        )
        process_clicked = st.form_submit_button("Process document", type="primary")
    if process_clicked:
        process_upload(uploaded_file, upload_category, chunking_method)
    st.caption("For bulk ingestion of many PDFs, use scripts/ingest.py --chunking-method <method> instead.")

    if st.session_state.upload_message:
        st.info(st.session_state.upload_message)


def render_query_tab() -> None:
    st.subheader("Ask a question")

    cases = fetch_cases()
    case_options = ["__all__"] + [c["case_id"] for c in cases]
    case_labels = {"__all__": "All documents (no case)", **{c["case_id"]: c["name"] for c in cases}}
    selected_case_id = st.selectbox(
        "Scope",
        options=case_options,
        format_func=lambda c: case_labels[c],
        help="Restrict retrieval to a single case's documents, or search everything. "
        "Manage cases and attach documents from the Cases tab.",
    )
    case_id = None if selected_case_id == "__all__" else selected_case_id

    st.text_area("Question", key="question", height=120)
    if st.button("Ask", type="primary"):
        answer_question(case_id)

    st.subheader("Answer")
    if st.session_state.answered_case_id:
        scoped_name = case_labels.get(st.session_state.answered_case_id, st.session_state.answered_case_id)
        st.caption(f"Scoped to case: {scoped_name}")
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
            with st.expander(f"[{citation['citation_id']}] {citation['document_name']} — Page {citation['page_number']}"):
                if citation.get("section"):
                    st.caption(f"Section: {citation['section']}")
                if citation.get("heading"):
                    st.caption(f"Heading: {citation['heading']}")
    else:
        st.write("No sources cited yet.")

    if st.session_state.trace_data:
        st.divider()
        display_trace(st.session_state.trace_data)


def render_evaluate_tab() -> None:
    st.subheader("Run an evaluation")
    st.caption(
        "Runs the reproducible retrieval-evaluation harness against data/evaluation_dataset.json "
        "and writes results to data/eval_runs/, same as scripts/run_evaluation.py."
    )
    col1, col2, col3 = st.columns(3)
    with col1:
        retrieval_method = st.selectbox(
            "Retrieval method", options=list(RETRIEVAL_METHOD_LABELS), format_func=lambda m: RETRIEVAL_METHOD_LABELS[m]
        )
    with col2:
        chunking_method = st.selectbox(
            "Chunking method (index to evaluate)",
            options=list(CHUNKING_METHOD_LABELS),
            format_func=lambda m: CHUNKING_METHOD_LABELS[m],
        )
    with col3:
        top_k = st.number_input("top_k", min_value=1, max_value=20, value=5)

    running = st.session_state.active_eval_run_id is not None
    if st.button("Run evaluation", type="primary", disabled=running):
        submit_evaluation(retrieval_method, chunking_method, int(top_k))
        st.rerun()

    if st.session_state.eval_message:
        st.error(st.session_state.eval_message)

    if st.session_state.active_eval_run_id:
        status = fetch_evaluation_status(st.session_state.active_eval_run_id)
        if status is None:
            st.warning("Could not reach the API to check evaluation status.")
        elif status["status"] in ("pending", "running"):
            with st.spinner(f"Evaluation {status['status']}…"):
                time.sleep(2)
                st.rerun()
        elif status["status"] == "done":
            st.success(f"Evaluation complete: {status['retrieval_method']} / {status['chunking_method']}")
            st.json(status["summary"])
            st.session_state.active_eval_run_id = None
        elif status["status"] == "failed":
            st.error(f"Evaluation failed: {status['error']}")
            st.session_state.active_eval_run_id = None

    st.divider()
    st.subheader("Past runs")
    runs = fetch_evaluation_runs()
    if not runs:
        st.info("No evaluation runs found yet.")
        return

    rows = []
    for run in runs:
        manifest = run["manifest"]
        overall = run["summary"].get("overall", {})
        rows.append(
            {
                "run": run["run_dir"],
                "retrieval": manifest.get("retrieval_method"),
                "chunking": manifest.get("chunking_method", "legal"),
                "recall@1": overall.get("recall_at_1"),
                "recall@3": overall.get("recall_at_3"),
                "recall@5": overall.get("recall_at_5"),
                "precision@5": overall.get("precision_at_5"),
                "mrr": overall.get("mrr"),
            }
        )
    st.dataframe(rows, use_container_width=True)


def render_cases_tab() -> None:
    st.subheader("Create a case")
    st.caption(
        "A case is a named collection of already-ingested documents. Attaching a document to a "
        "case never re-ingests it - the same document can belong to any number of cases."
    )
    with st.form("create_case_form", clear_on_submit=True):
        case_name = st.text_input("Case name", placeholder="e.g. Smith v. Jones")
        case_description = st.text_input("Description (optional)")
        create_clicked = st.form_submit_button("Create case", type="primary")
    if create_clicked:
        create_case(case_name, case_description)

    if st.session_state.case_message:
        st.info(st.session_state.case_message)

    st.divider()
    st.subheader("Attach documents to a case")
    cases = fetch_cases()
    documents = fetch_documents()

    if not cases:
        st.info("No cases yet - create one above.")
        return
    if not documents:
        st.info("No documents ingested yet - use the Ingest tab first.")
        return

    case_labels = {c["case_id"]: c["name"] for c in cases}
    target_case_id = st.selectbox(
        "Case", options=[c["case_id"] for c in cases], format_func=lambda c: case_labels[c], key="attach_case_id"
    )
    doc_labels = {d["document_id"]: f"{d['filename']} ({d['category'] or 'uncategorized'})" for d in documents}
    selected_doc_ids = st.multiselect(
        "Documents to attach", options=list(doc_labels), format_func=lambda d: doc_labels[d]
    )
    if st.button("Attach selected documents"):
        attach_documents_to_case(target_case_id, selected_doc_ids)
        st.rerun()

    st.divider()
    st.subheader("Cases")
    rows = [
        {
            "case": c["name"],
            "description": c.get("description") or "",
            "documents": len(c["document_ids"]),
        }
        for c in cases
    ]
    st.dataframe(rows, use_container_width=True)


def main() -> None:
    st.set_page_config(page_title="Legal Intelligence Assistant", page_icon="L", layout="wide")
    initialize_state()

    st.title("Legal Intelligence Assistant")
    st.write("Upload a text-based PDF, ask questions grounded in its contents, and compare retrieval/chunking strategies.")

    health = check_api_health()
    if health is None:
        st.error(f"Cannot reach the API at {API_BASE_URL}. Start it with: uvicorn src.api.main:app")
        return
    st.caption(
        f"API connected — {health['indexed_chunks']} chunks indexed "
        f"({health['embedding_model']}, chunking: {CHUNKING_METHOD_LABELS.get(health['chunking_method'], health['chunking_method'])})"
    )

    ingest_tab, query_tab, cases_tab, evaluate_tab = st.tabs(["Ingest", "Query", "Cases", "Evaluate"])
    with ingest_tab:
        render_ingest_tab(health)
    with query_tab:
        render_query_tab()
    with cases_tab:
        render_cases_tab()
    with evaluate_tab:
        render_evaluate_tab()


if __name__ == "__main__":
    main()
