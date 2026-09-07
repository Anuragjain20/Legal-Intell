"""Tests for the retrieval evaluation harness."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from src.embeddings.base import EmbeddedChunk
from src.evaluation.evaluator import EvaluationCase, RetrievalEvaluator
from src.ingestion.models import Chunk
from src.retrieval.retriever import Retriever
from src.vectorstore.local_store import LocalVectorStore
from src.vectorstore.service import VectorIndexService


class FakeEmbeddingProvider:
    model_name = "fake-model"
    model_version = "1"

    @property
    def embedding_dimension(self) -> int:
        return 4

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        lowered = text.lower()
        if "termination" in lowered or "end" in lowered or "terminate" in lowered:
            return [0.99, 0.01, 0.0, 0.0]
        if "payment" in lowered or "pay" in lowered or "money" in lowered:
            return [0.01, 0.99, 0.0, 0.0]
        if "confidential" in lowered or "secret" in lowered or "private" in lowered:
            return [0.0, 0.01, 0.99, 0.0]
        if "liability" in lowered or "responsible" in lowered or "responsible" in lowered:
            return [0.0, 0.0, 0.01, 0.99]
        return [0.25, 0.25, 0.25, 0.25]


def make_chunk(
    chunk_id: str,
    text: str,
    page_number: int,
    heading: str,
    section: str = "1",
    document_name: str = "Contract Act",
) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        document_id="doc-1",
        page_number=page_number,
        end_page_number=page_number,
        section=section,
        heading=heading,
        text=text,
        document_name=document_name,
        category="legal",
    )


def create_test_retriever(tmp_path: Path) -> Retriever:
    """Create a retriever with test data."""
    provider = FakeEmbeddingProvider()
    chunks = [
        make_chunk("c1", "Termination requires written notice and 30-day advance warning.", 1, "Termination", "Termination"),
        make_chunk("c2", "Payment is due within 30 days of invoice.", 2, "Payment", "Payment"),
        make_chunk("c3", "Confidential information must be protected with reasonable security.", 3, "Confidentiality", "Confidentiality"),
        make_chunk("c4", "Liability is limited to direct damages only.", 4, "Liability", "Liability"),
        make_chunk("c5", "Contract duration is one year with annual renewal.", 5, "Duration", "Duration"),
        make_chunk("c6", "Breach remedies include injunctive relief and damages.", 6, "Remedies", "Remedies"),
        make_chunk("c7", "Force Majeure events excuse performance obligations.", 7, "Force Majeure", "Force Majeure"),
        make_chunk("c8", "Party must indemnify against third-party claims.", 8, "Indemnification", "Indemnification"),
    ]

    embedded = [
        EmbeddedChunk(
            chunk=chunk,
            embedding=provider.embed_query(chunk.text),
            embedding_model=provider.model_name,
            embedding_version=provider.model_version,
        )
        for chunk in chunks
    ]
    store = LocalVectorStore(storage_dir=tmp_path / "vectorstore", dimension=4)
    VectorIndexService(store=store).index_embeddings(embedded)
    return Retriever(embedding_provider=provider, vector_store=store)


@pytest.fixture
def test_dataset_file(tmp_path: Path) -> Path:
    """Create a test evaluation dataset."""
    dataset = {
        "metadata": {
            "version": "1.0",
            "corpus": "Test",
            "total_questions": 6,
        },
        "questions": [
            {
                "id": "Q001",
                "question": "What are the termination conditions?",
                "expected_document": "Contract Act",
                "expected_section": "Termination",
                "question_type": "direct_definition",
                "context": "Test",
            },
            {
                "id": "Q002",
                "question": "How should payment be made?",
                "expected_document": "Contract Act",
                "expected_section": "Payment",
                "question_type": "direct_definition",
                "context": "Test",
            },
            {
                "id": "Q003",
                "question": "How does one end this contract?",
                "expected_document": "Contract Act",
                "expected_section": "Termination",
                "question_type": "paraphrased",
                "context": "Test",
            },
            {
                "id": "Q004",
                "question": "What happens if someone violates confidentiality?",
                "expected_document": "Contract Act",
                "expected_section": "Confidentiality",
                "question_type": "consequence_effect",
                "context": "Test",
            },
            {
                "id": "Q005",
                "question": "How do termination and payment relate?",
                "expected_document": "Contract Act",
                "expected_section": ["Termination", "Payment"],
                "question_type": "multi_section",
                "context": "Test",
            },
            {
                "id": "Q006",
                "question": "What is the exchange rate for cryptocurrency?",
                "expected_document": None,
                "expected_section": None,
                "question_type": "out_of_corpus",
                "context": "Test",
            },
        ],
    }

    dataset_path = tmp_path / "evaluation_dataset.json"
    with open(dataset_path, "w") as f:
        json.dump(dataset, f)

    return dataset_path


def test_evaluator_loads_dataset(tmp_path: Path, test_dataset_file: Path):
    """Test that evaluator loads the dataset correctly."""
    retriever = create_test_retriever(tmp_path)
    evaluator = RetrievalEvaluator(retriever, test_dataset_file)

    assert len(evaluator.dataset) == 6
    assert evaluator.dataset[0].id == "Q001"
    assert evaluator.dataset[0].question == "What are the termination conditions?"


def test_evaluator_single_question(tmp_path: Path, test_dataset_file: Path):
    """Test evaluation of a single question."""
    retriever = create_test_retriever(tmp_path)
    evaluator = RetrievalEvaluator(retriever, test_dataset_file)

    case = evaluator.dataset[0]
    metric = evaluator._evaluate_single(case, top_k=5)

    assert metric.case_id == "Q001"
    assert metric.question == "What are the termination conditions?"
    assert "Termination" in metric.retrieved_sections
    assert metric.rank_of_expected is not None
    assert 1 <= metric.rank_of_expected <= 5


def test_evaluator_out_of_corpus_detection(tmp_path: Path, test_dataset_file: Path):
    """Test that out-of-corpus questions are correctly identified."""
    retriever = create_test_retriever(tmp_path)
    evaluator = RetrievalEvaluator(retriever, test_dataset_file)

    case = evaluator.dataset[5]  # Out of corpus question
    metric = evaluator._evaluate_single(case, top_k=5)

    assert metric.is_out_of_corpus is True
    assert metric.rank_of_expected is None
    assert metric.retrieved_sections == []


def test_evaluator_multi_section(tmp_path: Path, test_dataset_file: Path):
    """Test evaluation of multi-section questions."""
    retriever = create_test_retriever(tmp_path)
    evaluator = RetrievalEvaluator(retriever, test_dataset_file)

    case = evaluator.dataset[4]  # Multi-section question
    metric = evaluator._evaluate_single(case, top_k=5)

    assert metric.expected_section == ["Termination", "Payment"]
    if metric.rank_of_expected is not None:
        assert metric.retrieved_sections[metric.rank_of_expected - 1] in ["Termination", "Payment"]


def test_evaluator_recall_at_k(tmp_path: Path, test_dataset_file: Path):
    """Test recall@k calculation."""
    retriever = create_test_retriever(tmp_path)
    evaluator = RetrievalEvaluator(retriever, test_dataset_file)
    results = evaluator.evaluate(top_k=5)

    assert 0 <= results.recall_at_1 <= 1
    assert 0 <= results.recall_at_3 <= 1
    assert 0 <= results.recall_at_5 <= 1
    assert results.recall_at_1 <= results.recall_at_3 <= results.recall_at_5


def test_evaluator_mrr_calculation(tmp_path: Path, test_dataset_file: Path):
    """Test MRR (Mean Reciprocal Rank) calculation."""
    retriever = create_test_retriever(tmp_path)
    evaluator = RetrievalEvaluator(retriever, test_dataset_file)
    results = evaluator.evaluate(top_k=5)

    assert 0 <= results.mrr <= 1
    assert isinstance(results.mrr, float)


def test_evaluator_metrics_by_type(tmp_path: Path, test_dataset_file: Path):
    """Test that metrics are calculated per question type."""
    retriever = create_test_retriever(tmp_path)
    evaluator = RetrievalEvaluator(retriever, test_dataset_file)
    results = evaluator.evaluate(top_k=5)

    assert "direct_definition" in results.metrics_by_type
    assert "paraphrased" in results.metrics_by_type
    assert "consequence_effect" in results.metrics_by_type
    assert "multi_section" in results.metrics_by_type

    for q_type, metrics in results.metrics_by_type.items():
        assert "count" in metrics
        assert "recall_at_1" in metrics
        assert "recall_at_3" in metrics
        assert "recall_at_5" in metrics
        assert "mrr" in metrics


def test_evaluator_no_answer_detection_rate(tmp_path: Path, test_dataset_file: Path):
    """Test out-of-corpus detection rate."""
    retriever = create_test_retriever(tmp_path)
    evaluator = RetrievalEvaluator(retriever, test_dataset_file)
    results = evaluator.evaluate(top_k=5)

    assert results.out_of_corpus_questions == 1
    assert results.no_answer_detection_rate == 1.0 / 6
    assert 0 <= results.no_answer_detection_rate <= 1


def test_evaluator_results_dict_serialization(tmp_path: Path, test_dataset_file: Path):
    """Test that results can be serialized to dict."""
    retriever = create_test_retriever(tmp_path)
    evaluator = RetrievalEvaluator(retriever, test_dataset_file)
    evaluator.evaluate(top_k=5)
    result_dict = evaluator.results_to_dict()

    assert "summary" in result_dict
    assert "metrics_by_type" in result_dict
    assert "individual_results" in result_dict

    summary = result_dict["summary"]
    assert "recall_at_1" in summary
    assert "recall_at_3" in summary
    assert "recall_at_5" in summary
    assert "mrr" in summary
    assert "no_answer_detection_rate" in summary


def test_evaluator_evaluation_case_parsing():
    """Test EvaluationCase dataclass parsing."""
    case_dict = {
        "id": "Q001",
        "question": "What are the termination conditions?",
        "expected_document": "Contract Act",
        "expected_section": "Termination",
        "question_type": "direct_definition",
        "context": "Test",
    }
    case = EvaluationCase(**case_dict)

    assert case.id == "Q001"
    assert case.expected_section == "Termination"


def test_evaluator_evaluation_case_multi_section_list():
    """Test EvaluationCase with multi-section list."""
    case_dict = {
        "id": "Q021",
        "question": "How do termination and breach relate?",
        "expected_document": "Contract Act",
        "expected_section": ["Termination", "Remedies"],
        "question_type": "multi_section",
        "context": "Test",
    }
    case = EvaluationCase(**case_dict)

    assert isinstance(case.expected_section, list)
    assert len(case.expected_section) == 2


def test_evaluator_ranking_accuracy(tmp_path: Path, test_dataset_file: Path):
    """Test that expected sections are correctly ranked."""
    retriever = create_test_retriever(tmp_path)
    evaluator = RetrievalEvaluator(retriever, test_dataset_file)
    results = evaluator.evaluate(top_k=5)

    in_corpus_results = [r for r in results.individual_results if not r.is_out_of_corpus]
    for metric in in_corpus_results:
        if metric.rank_of_expected is not None:
            assert metric.found_in_top_1 == (metric.rank_of_expected == 1)
            assert metric.found_in_top_3 == (metric.rank_of_expected in (1, 2, 3))
            assert metric.found_in_top_5 == (metric.rank_of_expected in (1, 2, 3, 4, 5))


def test_evaluator_handles_retrieval_errors(tmp_path: Path):
    """Test that evaluator gracefully handles retrieval errors."""
    dataset = {
        "metadata": {"version": "1.0", "corpus": "Test", "total_questions": 1},
        "questions": [
            {
                "id": "Q001",
                "question": "Test question that will fail",
                "expected_document": "Contract Act",
                "expected_section": "TestSection",
                "question_type": "direct_definition",
                "context": "Test",
            }
        ],
    }

    dataset_path = tmp_path / "evaluation_dataset.json"
    with open(dataset_path, "w") as f:
        json.dump(dataset, f)

    retriever = create_test_retriever(tmp_path)
    evaluator = RetrievalEvaluator(retriever, dataset_path)

    class FailingRetriever(Retriever):
        def retrieve(self, query, top_k=5, filters=None):
            raise ValueError("Test error")

    evaluator.retriever = FailingRetriever(
        embedding_provider=FakeEmbeddingProvider(),
        vector_store=retriever.vector_store,
    )

    case = evaluator.dataset[0]
    metric = evaluator._evaluate_single(case, top_k=5)

    assert metric.retrieved_sections == []
    assert metric.rank_of_expected is None
    assert metric.found_in_top_1 is False
