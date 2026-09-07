"""Retrieval-only evaluation harness for legal RAG pipeline."""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

from src.embeddings.base import EmbeddingProvider
from src.retrieval.retriever import Retriever
from src.vectorstore.base import VectorStore


@dataclass
class EvaluationCase:
    """A single evaluation test case."""

    id: str
    question: str
    expected_document: Optional[str]
    expected_section: Optional[str | list[str]]
    expected_chunk_id: Optional[str] = None
    question_type: str = "unknown"
    context: str = ""
    is_out_of_corpus: bool = False
    retrieved_sections: Optional[list] = None


@dataclass
class RetrievalMetric:
    """Metrics for a single query evaluation."""

    case_id: str
    question: str
    question_type: str
    expected_section: Optional[str | list[str]]
    expected_chunk_id: Optional[str]
    retrieved_sections: list[str]
    retrieved_chunk_ids: list[str]
    scores: list[float]
    rank_of_expected: Optional[int]
    found_in_top_1: bool
    found_in_top_3: bool
    found_in_top_5: bool
    is_out_of_corpus: bool
    error: Optional[str] = None


@dataclass
class EvaluationResults:
    """Complete evaluation results."""

    total_questions: int
    in_corpus_questions: int
    out_of_corpus_questions: int
    recall_at_1: float
    recall_at_3: float
    recall_at_5: float
    mrr: float
    no_answer_detection_rate: float
    metrics_by_type: dict[str, dict]
    individual_results: list[RetrievalMetric]


class RetrievalEvaluator:
    """Evaluate retrieval quality against a dataset."""

    def __init__(self, retriever: Retriever, dataset_path: Path):
        self.retriever = retriever
        self.dataset = self._load_dataset(dataset_path)
        self.results: list[RetrievalMetric] = []

    def _load_dataset(self, dataset_path: Path) -> list[EvaluationCase]:
        """Load evaluation dataset from JSON file."""
        with open(dataset_path, "r") as f:
            data = json.load(f)
        return [EvaluationCase(**q) for q in data["questions"]]

    def evaluate(self, top_k: int = 5) -> EvaluationResults:
        """Run evaluation on all test cases."""
        self.results = []

        for case in self.dataset:
            metric = self._evaluate_single(case, top_k)
            self.results.append(metric)

        return self._aggregate_results()

    def _evaluate_single(self, case: EvaluationCase, top_k: int) -> RetrievalMetric:
        """Evaluate a single test case."""
        is_out_of_corpus = case.is_out_of_corpus or case.expected_document is None

        if is_out_of_corpus:
            return RetrievalMetric(
                case_id=case.id,
                question=case.question,
                question_type=case.question_type,
                expected_section=case.expected_section,
                expected_chunk_id=case.expected_chunk_id,
                retrieved_sections=[],
                retrieved_chunk_ids=[],
                scores=[],
                rank_of_expected=None,
                found_in_top_1=False,
                found_in_top_3=False,
                found_in_top_5=False,
                is_out_of_corpus=True,
            )

        try:
            results = self.retriever.retrieve(case.question, top_k=top_k)
        except Exception as e:
            return RetrievalMetric(
                case_id=case.id,
                question=case.question,
                question_type=case.question_type,
                expected_section=case.expected_section,
                expected_chunk_id=case.expected_chunk_id,
                retrieved_sections=[],
                retrieved_chunk_ids=[],
                scores=[],
                rank_of_expected=None,
                found_in_top_1=False,
                found_in_top_3=False,
                found_in_top_5=False,
                is_out_of_corpus=False,
                error=str(e),
            )

        retrieved_sections = [
            result.record.section or "UNKNOWN"
            for result in results
        ]
        retrieved_chunk_ids = [result.record.chunk_id for result in results]
        scores = [float(result.score) for result in results]

        expected_sections = (
            case.expected_section if isinstance(case.expected_section, list)
            else [case.expected_section]
        )

        # Match by chunk_id first (most precise), then by section
        rank_of_expected = None
        if case.expected_chunk_id:
            for i, chunk_id in enumerate(retrieved_chunk_ids, 1):
                if chunk_id == case.expected_chunk_id:
                    rank_of_expected = i
                    break

        # Fall back to section matching if chunk_id not found
        if rank_of_expected is None:
            for i, retrieved_section in enumerate(retrieved_sections, 1):
                if retrieved_section in expected_sections:
                    rank_of_expected = i
                    break

        return RetrievalMetric(
            case_id=case.id,
            question=case.question,
            question_type=case.question_type,
            expected_section=case.expected_section,
            expected_chunk_id=case.expected_chunk_id,
            retrieved_sections=retrieved_sections,
            retrieved_chunk_ids=retrieved_chunk_ids,
            scores=scores,
            rank_of_expected=rank_of_expected,
            found_in_top_1=rank_of_expected == 1 if rank_of_expected else False,
            found_in_top_3=rank_of_expected in (1, 2, 3) if rank_of_expected else False,
            found_in_top_5=rank_of_expected in (1, 2, 3, 4, 5) if rank_of_expected else False,
            is_out_of_corpus=False,
        )

    def _aggregate_results(self) -> EvaluationResults:
        """Calculate aggregate metrics."""
        in_corpus = [r for r in self.results if not r.is_out_of_corpus]
        out_of_corpus = [r for r in self.results if r.is_out_of_corpus]

        if not in_corpus:
            return EvaluationResults(
                total_questions=len(self.results),
                in_corpus_questions=0,
                out_of_corpus_questions=len(out_of_corpus),
                recall_at_1=0.0,
                recall_at_3=0.0,
                recall_at_5=0.0,
                mrr=0.0,
                no_answer_detection_rate=1.0,
                metrics_by_type={},
                individual_results=self.results,
            )

        recall_at_1 = sum(1 for r in in_corpus if r.found_in_top_1) / len(in_corpus)
        recall_at_3 = sum(1 for r in in_corpus if r.found_in_top_3) / len(in_corpus)
        recall_at_5 = sum(1 for r in in_corpus if r.found_in_top_5) / len(in_corpus)

        mrr_scores = [
            1.0 / r.rank_of_expected
            for r in in_corpus
            if r.rank_of_expected is not None
        ]
        mrr = sum(mrr_scores) / len(in_corpus) if mrr_scores else 0.0

        no_answer_detection = len(out_of_corpus) / len(self.results) if self.results else 0.0

        metrics_by_type = self._calculate_metrics_by_type(in_corpus)

        return EvaluationResults(
            total_questions=len(self.results),
            in_corpus_questions=len(in_corpus),
            out_of_corpus_questions=len(out_of_corpus),
            recall_at_1=recall_at_1,
            recall_at_3=recall_at_3,
            recall_at_5=recall_at_5,
            mrr=mrr,
            no_answer_detection_rate=no_answer_detection,
            metrics_by_type=metrics_by_type,
            individual_results=self.results,
        )

    def _calculate_metrics_by_type(self, in_corpus: list[RetrievalMetric]) -> dict:
        """Calculate metrics grouped by question type."""
        by_type = {}
        for metric in in_corpus:
            q_type = metric.question_type
            if q_type not in by_type:
                by_type[q_type] = []
            by_type[q_type].append(metric)

        result = {}
        for q_type, metrics in by_type.items():
            count = len(metrics)
            r1 = sum(1 for m in metrics if m.found_in_top_1) / count if count > 0 else 0
            r3 = sum(1 for m in metrics if m.found_in_top_3) / count if count > 0 else 0
            r5 = sum(1 for m in metrics if m.found_in_top_5) / count if count > 0 else 0
            mrr_scores = [1.0 / m.rank_of_expected for m in metrics if m.rank_of_expected]
            mrr = sum(mrr_scores) / count if mrr_scores and count > 0 else 0

            result[q_type] = {
                "count": count,
                "recall_at_1": r1,
                "recall_at_3": r3,
                "recall_at_5": r5,
                "mrr": mrr,
            }

        return result

    def results_to_dict(self) -> dict:
        """Convert results to serializable dict."""
        aggregated = self._aggregate_results()
        return {
            "summary": {
                "total_questions": aggregated.total_questions,
                "in_corpus_questions": aggregated.in_corpus_questions,
                "out_of_corpus_questions": aggregated.out_of_corpus_questions,
                "recall_at_1": aggregated.recall_at_1,
                "recall_at_3": aggregated.recall_at_3,
                "recall_at_5": aggregated.recall_at_5,
                "mrr": aggregated.mrr,
                "no_answer_detection_rate": aggregated.no_answer_detection_rate,
            },
            "metrics_by_type": aggregated.metrics_by_type,
            "individual_results": [asdict(r) for r in aggregated.individual_results],
        }
