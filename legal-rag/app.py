"""Streamlit entry point for the local Legal RAG MVP."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from src.config.settings import Settings
from src.embeddings.providers import LocalHuggingFaceEmbeddingProvider
from src.embeddings.service import EmbeddingService
from src.generation.citations import CitationMapper
from src.generation.context_builder import ContextBuilder
from src.generation.exceptions import GenerationError
from src.generation.llm_service import GenerationService, LLMService
from src.generation.prompt import PromptBuilder
from src.generation.providers import DeepSeekLLMClient
from src.ingestion.exceptions import UploadValidationError
from src.ingestion.service import DocumentUploadService
from src.retrieval.exceptions import RetrievalError
from src.retrieval.retriever import Retriever
from src.vectorstore.chroma_store import ChromaVectorStore
from src.vectorstore.service import VectorIndexService
from src.evaluation.evaluator import RetrievalEvaluator


APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"
DOCUMENTS_DIR = DATA_DIR / "documents"
CHROMA_DIR = DATA_DIR / "chroma"
MAX_UPLOAD_SIZE_BYTES = 50 * 1024 * 1024
DEFAULT_QUESTION = "What are the termination conditions?"


@st.cache_resource
def build_services() -> tuple[DocumentUploadService, EmbeddingService, VectorIndexService, Retriever, GenerationService]:
    """Create the local pipeline once per Streamlit process."""
    settings = Settings.from_env(APP_DIR / ".env")
    embedding_provider = LocalHuggingFaceEmbeddingProvider(model_name=settings.embedding_model)
    embedding_service = EmbeddingService(provider=embedding_provider)
    vector_store = ChromaVectorStore(storage_dir=CHROMA_DIR, dimension=embedding_service.embedding_dimension())
    return (
        DocumentUploadService(storage_dir=DOCUMENTS_DIR, max_file_size_bytes=MAX_UPLOAD_SIZE_BYTES),
        embedding_service,
        VectorIndexService(store=vector_store),
        Retriever(
            embedding_provider=embedding_provider,
            vector_store=vector_store,
            similarity_threshold=settings.similarity_threshold,
        ),
        GenerationService(
            llm_service=LLMService(
                client=DeepSeekLLMClient(
                    api_key=settings.deepseek_api_key,
                    model_name=settings.deepseek_model,
                    base_url=settings.deepseek_base_url,
                )
            ),
            context_builder=ContextBuilder(),
            prompt_builder=PromptBuilder(),
            citation_mapper=CitationMapper(),
        ),
    )


def initialize_state() -> None:
    st.session_state.setdefault("question", DEFAULT_QUESTION)
    st.session_state.setdefault("last_answer", None)
    st.session_state.setdefault("citations", [])
    st.session_state.setdefault("upload_message", None)
    st.session_state.setdefault("trace_data", None)
    st.session_state.setdefault("evaluation_running", False)
    st.session_state.setdefault("evaluation_status", None)


def index_document(
    filename: str, content: bytes, category: str, services: tuple, source_path: str | None = None
) -> tuple[str, int]:
    """Upload, embed, and index one PDF, returning its display name and chunk count."""
    upload_service, embedding_service, index_service, _, _ = services
    metadata, extraction, chunks = upload_service.upload(
        filename, content, category=category, source_path=source_path
    )
    if not chunks:
        raise ValueError(f"{metadata.filename} has no extractable text. Scanned PDFs need OCR support.")
    index_service.index_embeddings(embedding_service.embed_chunks(chunks))
    return metadata.filename, len(chunks)


def process_upload(uploaded_file, category: str, services: tuple) -> None:
    if uploaded_file is None:
        st.session_state.upload_message = "Select a PDF before processing."
        return

    try:
        filename, chunk_count = index_document(uploaded_file.name, uploaded_file.getvalue(), category, services)
    except (UploadValidationError, ValueError) as exc:
        st.session_state.upload_message = str(exc)
        return

    st.session_state.upload_message = f"Indexed {filename} as '{category.strip() or 'uncategorized'}' ({chunk_count} chunks)."


def process_folder(folder_path: str, services: tuple) -> None:
    folder = Path(folder_path).expanduser()
    if not folder.is_dir():
        st.session_state.upload_message = "Enter a valid local folder path."
        return

    pdf_paths = [path for path in folder.rglob("*") if path.is_file() and path.suffix.lower() == ".pdf"]
    if not pdf_paths:
        st.session_state.upload_message = "No PDF files were found in that folder."
        return

    indexed = 0
    chunks = 0
    skipped = 0
    for pdf_path in pdf_paths:
        try:
            category = pdf_path.parent.name
            _, chunk_count = index_document(
                pdf_path.name, pdf_path.read_bytes(), category, services, source_path=str(pdf_path)
            )
            indexed += 1
            chunks += chunk_count
        except (OSError, UploadValidationError, ValueError):
            skipped += 1

    st.session_state.upload_message = (
        f"Folder indexing complete: {indexed} PDFs and {chunks} chunks indexed; "
        f"{skipped} skipped. Categories came from each PDF's parent folder."
    )


def display_trace_investigation() -> None:
    """Display advanced trace investigation tools for debugging."""
    trace = st.session_state.trace_data
    if not trace:
        return

    with st.expander("🔬 Trace Investigation & Debug Tools", expanded=False):
        st.markdown("### Advanced Pipeline Investigation")

        investigation_tabs = st.tabs(["Query Analysis", "Source Mapping", "Retrieval Ranking", "Debug Info"])

        with investigation_tabs[0]:  # Query Analysis
            st.markdown("### Query Processing")
            st.markdown(f"**Question:** `{trace.get('question', 'N/A')}`")

            retrieval_step = next((s for s in trace["steps"] if s["step"] == "1. Embedding & Retrieval"), None)
            if retrieval_step:
                st.markdown(f"**Embedding Status:** {retrieval_step.get('status', 'Unknown')}")
                st.markdown(f"**Results Retrieved:** {retrieval_step.get('retrieved_count', 0)}")

        with investigation_tabs[1]:  # Source Mapping
            st.markdown("### Source Citation Mapping")

            retrieval_step = next((s for s in trace["steps"] if s["step"] == "1. Embedding & Retrieval"), None)
            context_step = next((s for s in trace["steps"] if s["step"] == "2. Building Context"), None)

            if retrieval_step and context_step and "results" in retrieval_step and "sources" in context_step:
                st.markdown("**Retrieval → Context Selection**")

                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**All Retrieved (Top 10)**")
                    retrieved_text = "\n".join([
                        f"[{res['rank']}] Sec {res['section']} (Score: {res['score']}) - p.{res['page']}"
                        for res in retrieval_step["results"][:10]
                    ])
                    st.code(retrieved_text, language="text")

                with col2:
                    st.markdown("**Selected for Context**")
                    selected_text = "\n".join([
                        f"SOURCE_{src['rank']} Sec {src['section']} (Score: {src['score']}) ✓"
                        for src in context_step["sources"]
                    ])
                    st.code(selected_text, language="text")

        with investigation_tabs[2]:  # Retrieval Ranking
            st.markdown("### Ranking Analysis")

            retrieval_step = next((s for s in trace["steps"] if s["step"] == "1. Embedding & Retrieval"), None)
            if retrieval_step and "results" in retrieval_step:
                results = retrieval_step["results"]

                # Score statistics
                scores = [float(res["score"]) for res in results]
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Top Score", f"{max(scores):.4f}")
                with col2:
                    st.metric("Avg Score", f"{sum(scores)/len(scores):.4f}")
                with col3:
                    st.metric("Min Score", f"{min(scores):.4f}")

                # Ranking by section
                st.markdown("**Score by Section**")
                sections_data = {}
                for res in results:
                    sec = res["section"] or "Unknown"
                    if sec not in sections_data:
                        sections_data[sec] = []
                    sections_data[sec].append(float(res["score"]))

                ranking_text = "\n".join([
                    f"{sec:15} → Avg: {sum(scores)/len(scores):.4f} (n={len(scores)})"
                    for sec, scores in sorted(sections_data.items(), key=lambda x: max(x[1]), reverse=True)
                ])
                st.code(ranking_text, language="text")

        with investigation_tabs[3]:  # Debug Info
            st.markdown("### Debug Information")

            # Pipeline stats
            st.markdown("**Pipeline Statistics**")
            pipeline_info = {
                "Total Steps": len(trace["steps"]),
                "Status": "✅ Complete" if all(s.get("status", "").startswith(("✅", "❌")) for s in trace["steps"]) else "⏳ In Progress",
            }

            for key, value in pipeline_info.items():
                st.text(f"{key}: {value}")

            # Step details
            st.markdown("**Step-by-Step Breakdown**")
            for step in trace["steps"]:
                step_name = step.get("step", "Unknown")
                step_status = step.get("status", "Unknown")
                details = {k: v for k, v in step.items() if k not in ["step", "status", "results", "sources"]}

                with st.expander(f"{step_name} → {step_status}"):
                    if details:
                        st.json(details)
                    else:
                        st.text("No additional details")

            # Full trace export
            st.markdown("**Export Trace**")
            import json
            trace_json = json.dumps(trace, indent=2)
            st.download_button(
                label="Download Trace as JSON",
                data=trace_json,
                file_name="rag_trace.json",
                mime="application/json",
            )


def display_trace_tree() -> None:
    """Display the RAG pipeline trace in an interactive tree format with investigation tools."""
    trace = st.session_state.trace_data
    if not trace:
        return

    with st.expander("🔍 RAG Pipeline Trace & Investigation", expanded=False):
        st.markdown("### Pipeline Execution Flow")

        # Tabs for different trace views
        trace_tabs = st.tabs(["Pipeline Flow", "Retrieval Details", "Context Analysis", "Raw Data"])

        with trace_tabs[0]:  # Pipeline Flow
            for step in trace["steps"]:
                if "status" in step and step["status"].startswith("❌"):
                    st.error(f"**{step['step']}**: {step['status']}")
                    continue

                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(f"**{step['step']}**")
                with col2:
                    st.markdown(step.get("status", ""))

                if step["step"] == "1. Embedding & Retrieval" and "results" in step:
                    with st.container(border=True):
                        st.markdown(f"📊 Retrieved {step['retrieved_count']} chunks | Top score: {step['top_result_score']}")
                        for res in step["results"]:
                            with st.expander(
                                f"📄 [{res['rank']}] {res['document']} (p.{res['page']}) - Score: {res['score']}"
                            ):
                                col_a, col_b = st.columns(2)
                                with col_a:
                                    st.markdown(f"**Section:** {res['section']}")
                                with col_b:
                                    st.markdown(f"**Heading:** {res['heading']}")
                                st.markdown(f"**Preview:** {res['snippet']}")

                elif step["step"] == "2. Building Context" and "sources" in step:
                    with st.container(border=True):
                        st.markdown(
                            f"✂️ Selected {step['sources_selected']} sources | "
                            f"Context: {step['context_length']:,} chars"
                        )
                        for src in step["sources"]:
                            st.markdown(
                                f"  • **[SOURCE_{src['rank']}]** {src['document']} (p.{src['page']}) - "
                                f"Score: {src['score']} | {src['heading'] or src['section']}"
                            )

                elif step["step"] == "3. LLM Generation":
                    with st.container(border=True):
                        cols = st.columns(3)
                        with cols[0]:
                            st.metric("Model", step["model"], delta=None)
                        with cols[1]:
                            st.metric("Citations", step["citations_found"])
                        with cols[2]:
                            st.metric("Answer Length", f"{step['answer_length']} chars")

        with trace_tabs[1]:  # Retrieval Details
            retrieval_step = next((s for s in trace["steps"] if s["step"] == "1. Embedding & Retrieval"), None)
            if retrieval_step and "results" in retrieval_step:
                st.markdown("### Retrieved Chunks (Top 10)")
                retrieval_df_data = []
                for res in retrieval_step["results"][:10]:
                    retrieval_df_data.append({
                        "Rank": res["rank"],
                        "Score": float(res["score"]),
                        "Section": res["section"],
                        "Page": res["page"],
                        "Document": res["document"],
                        "Text": res["snippet"][:80] + "..."
                    })
                if retrieval_df_data:
                    import pandas as pd
                    df = pd.DataFrame(retrieval_df_data)
                    st.dataframe(df, use_container_width=True, hide_index=True)

                    # Show score distribution
                    st.markdown("### Score Distribution")
                    scores = [float(res["score"]) for res in retrieval_step["results"]]
                    st.bar_chart({
                        "Score": scores,
                        "Rank": list(range(1, len(scores) + 1))
                    })

        with trace_tabs[2]:  # Context Analysis
            context_step = next((s for s in trace["steps"] if s["step"] == "2. Building Context"), None)
            if context_step and "sources" in context_step:
                st.markdown("### Selected Context Sources")
                st.markdown(f"**Total selected:** {context_step['sources_selected']} sources")
                st.markdown(f"**Context size:** {context_step['context_length']:,} characters")

                for src in context_step["sources"]:
                    with st.expander(f"SOURCE_{src['rank']} - {src['document']} (p.{src['page']})"):
                        st.markdown(f"**Score:** `{src['score']}`")
                        st.markdown(f"**Section:** `{src['section'] or 'N/A'}`")
                        st.markdown(f"**Heading:** `{src['heading'] or 'N/A'}`")

        with trace_tabs[3]:  # Raw Data
            st.markdown("### Raw Trace JSON")
            st.json(trace)


def run_evaluation(retriever: Retriever) -> None:
    """Run retrieval evaluation and save results."""
    import json

    dataset_path = DATA_DIR / "evaluation_dataset.json"
    results_path = DATA_DIR / "evaluation_results.json"

    if not dataset_path.exists():
        st.session_state.evaluation_status = "❌ Evaluation dataset not found"
        return

    try:
        st.session_state.evaluation_status = "🔄 Running evaluation..."
        st.rerun()

        evaluator = RetrievalEvaluator(retriever, dataset_path)
        results = evaluator.evaluate(top_k=5)
        results_dict = evaluator.results_to_dict()

        with open(results_path, "w") as f:
            json.dump(results_dict, f, indent=2)

        st.session_state.evaluation_status = (
            f"✅ Evaluation complete! "
            f"Recall@1: {results.recall_at_1:.4f}, "
            f"Recall@3: {results.recall_at_3:.4f}, "
            f"Recall@5: {results.recall_at_5:.4f}, "
            f"MRR: {results.mrr:.4f}"
        )
    except Exception as e:
        st.session_state.evaluation_status = f"❌ Evaluation failed: {str(e)}"


def answer_question(services: tuple) -> None:
    settings = Settings.from_env(APP_DIR / ".env")
    if not settings.deepseek_api_key:
        st.session_state.last_answer = "Set DEEPSEEK_API_KEY in .env before asking questions."
        st.session_state.citations = []
        st.session_state.trace_data = None
        return

    _, _, _, retriever, generation_service = services
    trace_data = {"question": st.session_state.question, "steps": []}

    try:
        trace_data["steps"].append({"step": "1. Embedding Query", "status": "🔄 Processing..."})

        results = retriever.retrieve(st.session_state.question, top_k=8)
        trace_data["steps"][-1] = {
            "step": "1. Embedding & Retrieval",
            "status": "✅ Complete",
            "retrieved_count": len(results),
            "top_result_score": f"{results[0].score:.4f}" if results else "N/A",
            "results": [
                {
                    "rank": r.rank,
                    "document": r.record.document_name or r.record.document_id,
                    "page": r.record.page_number,
                    "section": r.record.section or "N/A",
                    "heading": r.record.heading or "N/A",
                    "score": f"{r.score:.4f}",
                    "snippet": r.record.text[:100] + "..." if len(r.record.text) > 100 else r.record.text,
                }
                for r in results
            ],
        }

        trace_data["steps"].append({"step": "2. Building Context", "status": "🔄 Processing..."})

        result = generation_service.answer(st.session_state.question, results)

        trace_data["steps"][-1] = {
            "step": "2. Building Context",
            "status": "✅ Complete",
            "sources_selected": len(result.used_context.sources),
            "context_length": len(result.used_context.rendered_context),
            "sources": [
                {
                    "rank": s.rank,
                    "document": s.document_name or s.document_id,
                    "page": s.page_number,
                    "section": s.section or "N/A",
                    "heading": s.heading or "N/A",
                    "score": f"{s.score:.4f}",
                }
                for s in result.used_context.sources
            ],
        }

        trace_data["steps"].append(
            {
                "step": "3. LLM Generation",
                "status": "✅ Complete",
                "model": result.model,
                "citations_found": len(result.citations),
                "answer_length": len(result.answer),
            }
        )

    except (RetrievalError, GenerationError, ValueError) as exc:
        trace_data["steps"].append({"step": "❌ Error", "status": str(exc)})
        st.session_state.last_answer = str(exc)
        st.session_state.citations = []
        st.session_state.trace_data = trace_data
        return

    st.session_state.last_answer = result.answer
    st.session_state.citations = result.citations or []
    st.session_state.trace_data = trace_data


def main() -> None:
    st.set_page_config(page_title="Legal Intelligence Assistant", page_icon="L", layout="wide")
    initialize_state()

    st.title("Legal Intelligence Assistant")
    st.write("Upload a text-based PDF, then ask questions grounded in its contents.")

    try:
        services = build_services()
    except ImportError as exc:
        st.error(f"Missing dependency: {exc}. Run: pip install -r requirements.txt")
        return

    st.subheader("Index documents")
    upload_tab, folder_tab = st.tabs(["Upload PDF", "Index local folder"])
    with upload_tab:
        with st.form("upload_form", clear_on_submit=True):
            uploaded_file = st.file_uploader("PDF document", type=["pdf"])
            upload_category = st.text_input("Category", value="general", help="Examples: contracts, employment, policies")
            process_clicked = st.form_submit_button("Process document", type="primary")
        if process_clicked:
            process_upload(uploaded_file, upload_category, services)

    with folder_tab:
        with st.form("folder_form"):
            folder_path = st.text_input("Folder path", placeholder=r"C:\\Documents\\legal-pdfs")
            st.caption("Each PDF is copied into a category named after its immediate parent folder.")
            folder_clicked = st.form_submit_button("Index folder", type="primary")
        if folder_clicked:
            process_folder(folder_path, services)

    if st.session_state.upload_message:
        st.info(st.session_state.upload_message)

    st.divider()
    st.subheader("Ask a question")
    st.text_area("Question", key="question", height=120)
    if st.button("Ask", type="primary"):
        answer_question(services)

    st.subheader("Answer")
    if st.session_state.last_answer:
        st.write(st.session_state.last_answer)
    else:
        st.info("Process a document and ask a question to receive a grounded answer.")

    st.subheader("Sources")
    citations = st.session_state.citations
    if citations:
        for citation in citations:
            st.write(f"[{citation.citation_id}] {citation.document_name} - Page {citation.page_number}")
    else:
        st.write("No sources cited yet.")

    st.divider()
    st.subheader("🧪 Model Testing & Evaluation")

    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown("Run retrieval evaluation against a curated dataset to measure baseline performance.")
    with col2:
        if st.button("Run Evaluation", type="secondary", key="eval_button"):
            st.session_state.evaluation_running = True

    if st.session_state.evaluation_running:
        _, _, _, retriever, _ = services
        run_evaluation(retriever)
        st.session_state.evaluation_running = False

    if st.session_state.evaluation_status:
        if "✅" in st.session_state.evaluation_status:
            st.success(st.session_state.evaluation_status)
            st.info("📊 View detailed results in the **Evaluation** page in the sidebar")
        elif "❌" in st.session_state.evaluation_status:
            st.error(st.session_state.evaluation_status)
        else:
            st.info(st.session_state.evaluation_status)

    st.divider()
    display_trace_tree()
    display_trace_investigation()


if __name__ == "__main__":
    main()
