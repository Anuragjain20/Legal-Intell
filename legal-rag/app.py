"""Streamlit application entry point for the Legal RAG scaffold."""

from pathlib import Path

import streamlit as st

from src.ingestion.exceptions import UploadValidationError
from src.ingestion.service import DocumentUploadService


APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"
DOCUMENTS_DIR = DATA_DIR / "documents"

DEFAULT_QUESTION = "What are the termination conditions?"
PLACEHOLDER_ANSWER = "RAG response will appear here..."
PLACEHOLDER_SOURCE = "Document - Page X"
MAX_UPLOAD_SIZE_BYTES = 50 * 1024 * 1024


def initialize_state() -> None:
    st.session_state.setdefault("question", DEFAULT_QUESTION)
    st.session_state.setdefault("last_answer", PLACEHOLDER_ANSWER)
    st.session_state.setdefault("sources", [PLACEHOLDER_SOURCE])
    st.session_state.setdefault("uploaded_file_name", None)
    st.session_state.setdefault("ask_clicked", False)
    st.session_state.setdefault("upload_message", None)
    st.session_state.setdefault("upload_success", None)


def handle_ask() -> None:
    st.session_state.ask_clicked = True
    st.session_state.last_answer = "Retrieval pipeline not connected yet."
    st.session_state.sources = [PLACEHOLDER_SOURCE]


def handle_upload(uploaded_file) -> None:
    if uploaded_file is None:
        st.session_state.upload_message = None
        st.session_state.upload_success = None
        return

    service = DocumentUploadService(
        storage_dir=DOCUMENTS_DIR,
        max_file_size_bytes=MAX_UPLOAD_SIZE_BYTES,
    )

    try:
        metadata, _extraction, _chunks = service.upload(uploaded_file.name, uploaded_file.getvalue())
    except UploadValidationError as exc:
        st.session_state.upload_message = str(exc)
        st.session_state.upload_success = False
        st.session_state.uploaded_file_name = None
        return

    st.session_state.upload_message = (
        f"Uploaded {metadata.filename} ({metadata.file_size} bytes)."
    )
    st.session_state.upload_success = True
    st.session_state.uploaded_file_name = metadata.filename


def render_header() -> None:
    st.title("Legal Intelligence Assistant")
    st.write("Ask questions about your legal documents.")


def render_upload_section() -> None:
    st.subheader("Upload documents")
    uploaded_file = st.file_uploader("Browse files", type=["pdf"])
    handle_upload(uploaded_file)

    if st.session_state.upload_message:
        if st.session_state.upload_success:
            st.success(st.session_state.upload_message)
        else:
            st.error(st.session_state.upload_message)


def render_question_section() -> None:
    st.subheader("Ask a question")
    st.text_area("Question", key="question", height=120)
    st.button("Ask", type="primary", on_click=handle_ask)


def render_answer_section() -> None:
    st.subheader("Answer")
    if st.session_state.ask_clicked:
        st.success(st.session_state.last_answer)
    else:
        st.info(PLACEHOLDER_ANSWER)


def render_sources_section() -> None:
    st.subheader("Sources")
    sources = st.session_state.sources or []
    if sources:
        for source in sources:
            st.write(f"- {source}")
    else:
        st.write("- Document - Page X")


def render_footer() -> None:
    st.caption(
        "The document pipeline, embeddings, retrieval, and generation layers "
        "will be connected in later stories."
    )


def main() -> None:
    st.set_page_config(
        page_title="Legal Intelligence Assistant",
        page_icon="L",
        layout="wide",
    )

    initialize_state()
    render_header()
    render_upload_section()
    st.divider()
    render_question_section()
    st.divider()
    render_answer_section()
    render_sources_section()
    render_footer()


if __name__ == "__main__":
    main()
