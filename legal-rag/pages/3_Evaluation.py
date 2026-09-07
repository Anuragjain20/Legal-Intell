"""Streamlit page for retrieval evaluation results and analysis."""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st
import pandas as pd

APP_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = APP_DIR / "data"
DATASET_PATH = DATA_DIR / "evaluation_dataset.json"
RESULTS_PATH = DATA_DIR / "evaluation_results.json"


def load_dataset() -> dict:
    """Load the evaluation dataset."""
    if not DATASET_PATH.exists():
        return None
    with open(DATASET_PATH, "r") as f:
        return json.load(f)


def load_results() -> dict:
    """Load the evaluation results."""
    if not RESULTS_PATH.exists():
        return None
    with open(RESULTS_PATH, "r") as f:
        return json.load(f)


def display_summary_metrics(results: dict) -> None:
    """Display summary metrics in metric cards."""
    summary = results.get("summary", {})

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(
            "Recall@1",
            f"{summary.get('recall_at_1', 0):.4f}",
            help="Fraction of questions where expected section is in top 1 result",
        )
    with col2:
        st.metric(
            "Recall@3",
            f"{summary.get('recall_at_3', 0):.4f}",
            help="Fraction of questions where expected section is in top 3 results",
        )
    with col3:
        st.metric(
            "Recall@5",
            f"{summary.get('recall_at_5', 0):.4f}",
            help="Fraction of questions where expected section is in top 5 results",
        )
    with col4:
        st.metric(
            "MRR",
            f"{summary.get('mrr', 0):.4f}",
            help="Mean Reciprocal Rank - average of 1/rank for found queries",
        )

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(
            "Total Questions",
            summary.get("total_questions", 0),
        )
    with col2:
        st.metric(
            "In-Corpus Questions",
            summary.get("in_corpus_questions", 0),
        )
    with col3:
        st.metric(
            "Out-of-Corpus Detection Rate",
            f"{summary.get('no_answer_detection_rate', 0):.4f}",
            help="Proportion of questions correctly identified as out of corpus",
        )


def display_metrics_by_type(results: dict) -> None:
    """Display metrics grouped by question type."""
    metrics_by_type = results.get("metrics_by_type", {})

    if not metrics_by_type:
        st.info("No metrics by type available.")
        return

    df_data = []
    for q_type, metrics in metrics_by_type.items():
        df_data.append({
            "Question Type": q_type.replace("_", " ").title(),
            "Count": metrics["count"],
            "Recall@1": f"{metrics['recall_at_1']:.4f}",
            "Recall@3": f"{metrics['recall_at_3']:.4f}",
            "Recall@5": f"{metrics['recall_at_5']:.4f}",
            "MRR": f"{metrics['mrr']:.4f}",
        })

    df = pd.DataFrame(df_data)
    st.dataframe(df, use_container_width=True, hide_index=True)


def display_individual_results(results: dict, dataset: dict) -> None:
    """Display individual test case results."""
    individual = results.get("individual_results", [])

    if not individual:
        st.info("No individual results available.")
        return

    filter_type = st.selectbox(
        "Filter by question type",
        ["All"] + sorted(list(set(r["question_type"] for r in individual if not r["is_out_of_corpus"]))),
    )

    filtered_results = [
        r for r in individual
        if filter_type == "All" or r["question_type"] == filter_type
    ]

    results_df_data = []
    for r in filtered_results:
        question_type = r["question_type"]
        expected_section = r["expected_section"]
        rank = r["rank_of_expected"]
        found_status = "✅" if rank else "❌"

        if r["is_out_of_corpus"]:
            found_status = "🚫 Out-of-Corpus"
            rank_display = "N/A"
        else:
            rank_display = str(rank) if rank else "Not found"

        results_df_data.append({
            "Question ID": r["case_id"],
            "Type": question_type.replace("_", " ").title(),
            "Question": r["question"][:50] + "..." if len(r["question"]) > 50 else r["question"],
            "Expected": str(expected_section),
            "Rank": rank_display,
            "Status": found_status,
            "Top Sections": ", ".join(r["retrieved_sections"][:3]) if r["retrieved_sections"] else "None",
        })

    df = pd.DataFrame(results_df_data)
    st.dataframe(df, use_container_width=True, hide_index=True)


def display_detailed_case(results: dict, case_id: str) -> None:
    """Display detailed information for a single test case."""
    individual = results.get("individual_results", [])
    case = next((r for r in individual if r["case_id"] == case_id), None)

    if not case:
        st.error("Case not found")
        return

    st.markdown(f"## {case['case_id']}: {case['question_type'].replace('_', ' ').title()}")
    st.markdown(f"**Question:** {case['question']}")
    st.markdown(f"**Type:** {case['question_type'].replace('_', ' ').title()}")

    if case["is_out_of_corpus"]:
        st.info("🚫 This question is outside the corpus - no answer expected.")
        return

    st.markdown(f"**Expected Section:** {case['expected_section']}")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Found in Top 1", "✅" if case["found_in_top_1"] else "❌")
    with col2:
        st.metric("Found in Top 3", "✅" if case["found_in_top_3"] else "❌")
    with col3:
        st.metric("Found in Top 5", "✅" if case["found_in_top_5"] else "❌")

    if case["rank_of_expected"]:
        st.success(f"✅ Expected section found at rank {case['rank_of_expected']}")
    else:
        st.error("❌ Expected section not found in top results")

    st.markdown("### Retrieved Sections (Top 5)")
    retrieved_data = []
    for i, (section, score) in enumerate(zip(case["retrieved_sections"], case["scores"]), 1):
        retrieved_data.append({
            "Rank": i,
            "Section": section,
            "Score": f"{score:.4f}",
            "Match": "✅ Expected" if section == case["expected_section"] else "—",
        })

    df = pd.DataFrame(retrieved_data)
    st.dataframe(df, use_container_width=True, hide_index=True)


def display_comparison_chart(results: dict) -> None:
    """Display recall comparison across different values of k."""
    summary = results.get("summary", {})

    recall_data = {
        "k": ["@1", "@3", "@5"],
        "Recall": [
            summary.get("recall_at_1", 0),
            summary.get("recall_at_3", 0),
            summary.get("recall_at_5", 0),
        ],
    }
    df = pd.DataFrame(recall_data)
    st.bar_chart(df.set_index("k"))


def main() -> None:
    st.set_page_config(page_title="Retrieval Evaluation", page_icon="📊", layout="wide")

    st.title("📊 Retrieval Evaluation Dashboard")
    st.write("Analysis of retrieval quality against the evaluation dataset.")

    results = load_results()
    dataset = load_dataset()

    if not results:
        st.error("❌ Evaluation results not found. Please run the evaluation first.")
        st.info("To run the evaluation, use the button in the main app or execute `python run_evaluation.py`")
        return

    if not dataset:
        st.error("❌ Evaluation dataset not found.")
        return

    st.divider()

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["Summary Metrics", "By Question Type", "Individual Results", "Case Details", "Comparison"]
    )

    with tab1:
        st.markdown("### Overall Performance Metrics")
        display_summary_metrics(results)

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("### Interpretation Guide")
            st.markdown("""
            - **Recall@k**: Percentage of questions where the correct section appears in the top-k results
            - **MRR (Mean Reciprocal Rank)**: Average of 1/rank across all questions (higher is better)
            - **Out-of-Corpus Detection**: Rate of correctly identifying questions outside the corpus
            """)

        with col2:
            st.markdown("### Baseline Targets")
            st.markdown("""
            - **Good Recall@1**: > 0.70 (70%)
            - **Good Recall@3**: > 0.85 (85%)
            - **Good Recall@5**: > 0.90 (90%)
            - **Good MRR**: > 0.75
            - **Good OOC Detection**: Close to question ratio
            """)

    with tab2:
        st.markdown("### Performance by Question Type")
        display_metrics_by_type(results)

        st.markdown("### Type Descriptions")
        st.markdown("""
        - **Direct Definition**: Straightforward questions about specific clauses
        - **Section Specific**: Questions explicitly referencing sections
        - **Paraphrased**: Same information but worded differently
        - **Consequence/Effect**: Questions about what happens when conditions occur
        - **Multi-Section**: Questions requiring information from multiple sections
        - **Out-of-Corpus**: Questions about information not in the corpus
        """)

    with tab3:
        st.markdown("### Individual Test Case Results")
        display_individual_results(results, dataset)

    with tab4:
        st.markdown("### Detailed Case Analysis")

        individual = results.get("individual_results", [])
        case_options = [r["case_id"] + " - " + r["question"][:40] for r in individual]
        selected = st.selectbox("Select a test case", case_options)

        if selected:
            case_id = selected.split(" ")[0]
            display_detailed_case(results, case_id)

    with tab5:
        st.markdown("### Recall Curve")
        display_comparison_chart(results)

        st.markdown("### Statistics")
        summary = results.get("summary", {})
        st.markdown(f"""
        - Questions evaluated: {summary.get('total_questions', 0)}
        - In-corpus: {summary.get('in_corpus_questions', 0)}
        - Out-of-corpus: {summary.get('out_of_corpus_questions', 0)}
        """)


if __name__ == "__main__":
    main()
