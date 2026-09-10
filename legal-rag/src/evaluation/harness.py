"""Retrieval evaluation harness for the legal-rag pipeline.

Loads the ground-truth dataset (data/evaluation_dataset.json), runs every
in-corpus question through a live Retriever, and scores a retrieved chunk
as relevant when it comes from an expected document AND its text contains
one of the expected answer spans (src/evaluation/matching.py). Metrics are
computed with the existing functions in src/evaluation/metrics.py so there
is exactly one implementation of Recall@K / Precision@K / MRR in the
codebase.

Unanswerable cases are run through the same retriever, end to end - they
are scored on whether the system's own confidence gate (the similarity
threshold that makes Retriever.retrieve raise NoRelevantResultsError) would
correctly withhold an answer, not skipped before retrieval is attempted.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from src.evaluation.matching import DOCUMENT_SEPARATOR, span_matches, split_multi_span
from src.evaluation.metrics import calculate_mrr, calculate_precision_at_k, calculate_recall_at_k
from src.retrieval.exceptions import NoRelevantResultsError

K_VALUES = (1, 3, 5)


@dataclass
class CaseResult:
    """Per-question evaluation outcome."""

    case_id: str
    question_type: str
    is_out_of_corpus: bool
    retrieved_chunk_ids: list[str] = field(default_factory=list)
    relevant_chunk_ids: list[str] = field(default_factory=list)
    top_score: float | None = None
    refused: bool = False
    error: str | None = None
    recall_at_k: dict[int, float] = field(default_factory=dict)
    precision_at_5: float = 0.0
    mrr: float = 0.0


@dataclass
class EvaluationSummary:
    """Aggregate metrics across the dataset, overall and per category."""

    total_cases: int
    in_corpus_cases: int
    unanswerable_cases: int
    overall: dict[str, float]
    by_question_type: dict[str, dict[str, float]]
    unanswerable_confidence_gate_rate: float | None
    case_results: list[CaseResult]


def load_dataset(dataset_path: Path) -> dict:
    return json.loads(dataset_path.read_text(encoding="utf-8"))


def _find_relevant_chunk_ids(
    documents: list[str],
    spans: list[str],
    chunks_by_document: dict[str, list[tuple[str, str]]],
) -> list[str]:
    """Return every chunk_id anywhere in the index whose text satisfies one
    of the expected (document, span) pairs - the full ground-truth universe,
    not just whichever of those chunks happened to be retrieved.

    This must scan the whole index (chunks_by_document, built once per
    run from vector_store.get_all() - see build_relevant_chunk_index)
    rather than only the chunks a retriever actually returned. Scoping the
    search to `retrieved` would make relevant_chunk_ids a subset of
    retrieved_chunk_ids by construction, which silently caps
    Recall@K's denominator to whatever was found and inflates recall
    toward 1.0 on any partial hit - exactly the bug this replaces.

    A multi-document comparison case (one span per document) needs each
    span matched against its own document; a single-document multi-span
    case needs every span matched against the same document's chunks.
    """
    if len(documents) == 1 and len(spans) > 1:
        documents = documents * len(spans)

    relevant: list[str] = []
    for doc_name, span in zip(documents, spans):
        for chunk_id, text in chunks_by_document.get(doc_name, []):
            if span_matches(span, text):
                relevant.append(chunk_id)
    return relevant


def build_relevant_chunk_index(vector_store) -> dict[str, list[tuple[str, str]]]:
    """Return {document_name: [(chunk_id, text), ...]} for every indexed
    chunk - the ground-truth universe evaluate_case scores retrieval
    against. Call once per run (not per question) and pass the result to
    run_evaluation/evaluate_case; vector_store only needs get_all()."""
    by_document: dict[str, list[tuple[str, str]]] = {}
    for record in vector_store.get_all():
        by_document.setdefault(record.document_name, []).append((record.chunk_id, record.text))
    return by_document


def evaluate_case(
    retriever, case: dict, chunks_by_document: dict[str, list[tuple[str, str]]], top_k: int = 5
) -> CaseResult:
    """Evaluate one dataset question. `retriever` needs only a
    `retrieve(question, top_k) -> list[chunk with .record]` method that
    raises NoRelevantResultsError on no candidates - Retriever itself, or
    any of the adapters in retriever_adapters.py. `chunks_by_document` is
    the whole index's ground-truth universe (build_relevant_chunk_index),
    used to score recall against every relevant chunk that exists, not
    just whichever ones were retrieved."""
    result = CaseResult(
        case_id=case["id"],
        question_type=case["question_type"],
        is_out_of_corpus=bool(case.get("is_out_of_corpus")),
    )

    try:
        retrieved = retriever.retrieve(case["question"], top_k=top_k)
    except NoRelevantResultsError:
        result.refused = True
        return result
    except Exception as exc:  # noqa: BLE001 - record and continue, don't abort the run
        result.error = f"{type(exc).__name__}: {exc}"
        return result

    result.retrieved_chunk_ids = [chunk.record.chunk_id for chunk in retrieved]
    result.top_score = retrieved[0].score if retrieved else None

    if result.is_out_of_corpus:
        return result

    documents = case["expected_document"].split(DOCUMENT_SEPARATOR)
    spans = split_multi_span(case["expected_answer_span"])
    result.relevant_chunk_ids = _find_relevant_chunk_ids(documents, spans, chunks_by_document)

    if result.relevant_chunk_ids:
        for k in K_VALUES:
            result.recall_at_k[k] = calculate_recall_at_k(
                result.relevant_chunk_ids, result.retrieved_chunk_ids, k
            )
        result.precision_at_5 = calculate_precision_at_k(
            result.relevant_chunk_ids, result.retrieved_chunk_ids, 5
        )
        result.mrr = calculate_mrr(result.relevant_chunk_ids, result.retrieved_chunk_ids)
    else:
        result.recall_at_k = {k: 0.0 for k in K_VALUES}
        result.precision_at_5 = 0.0
        result.mrr = 0.0

    return result


def run_evaluation(
    retriever,
    dataset: dict,
    similarity_threshold: float | None,
    chunks_by_document: dict[str, list[tuple[str, str]]],
    top_k: int = 5,
) -> EvaluationSummary:
    """Run every dataset question through `retriever` and score the results.

    `retriever` only needs a `retrieve(question, top_k) -> list` method that
    raises NoRelevantResultsError on no candidates - see
    src/evaluation/retriever_adapters.py for BM25/hybrid/reranked wrappers
    around Retriever's shape.

    `chunks_by_document` is the whole index's ground-truth universe (see
    build_relevant_chunk_index) - built once per run and passed to every
    evaluate_case call so Recall@K is scored against every relevant chunk
    that exists, not just whichever ones a given question's retrieval
    happened to return.

    `similarity_threshold` gates the "did the confidence gate correctly
    withhold an answer" metric on the unanswerable cases. Pass None when the
    retrieval method's score scale isn't a cosine similarity comparable to
    this threshold (BM25's unbounded scores, hybrid's ~0.03-scale RRF
    scores) - the gate rate is then reported as None rather than computed
    against a threshold that doesn't apply to that scale.
    """
    all_results = [
        evaluate_case(retriever, case, chunks_by_document, top_k=top_k) for case in dataset["questions"]
    ]

    in_corpus = [r for r in all_results if not r.is_out_of_corpus]
    unanswerable = [r for r in all_results if r.is_out_of_corpus]

    overall = _aggregate(in_corpus)
    by_type: dict[str, dict[str, float]] = {}
    types = sorted({r.question_type for r in in_corpus})
    for q_type in types:
        by_type[q_type] = _aggregate([r for r in in_corpus if r.question_type == q_type])

    gate_rate: float | None
    if similarity_threshold is None:
        gate_rate = None
    else:
        # A refusal (NoRelevantResultsError) or a top score already below the
        # configured threshold both count as the confidence gate correctly
        # withholding an answer for a question that has no real evidence.
        gated = sum(
            1
            for r in unanswerable
            if r.refused or (r.top_score is not None and r.top_score < similarity_threshold)
        )
        gate_rate = gated / len(unanswerable) if unanswerable else 0.0

    return EvaluationSummary(
        total_cases=len(all_results),
        in_corpus_cases=len(in_corpus),
        unanswerable_cases=len(unanswerable),
        overall=overall,
        by_question_type=by_type,
        unanswerable_confidence_gate_rate=gate_rate,
        case_results=all_results,
    )


def _aggregate(results: list[CaseResult]) -> dict[str, float]:
    if not results:
        return {"count": 0, "recall_at_1": 0.0, "recall_at_3": 0.0, "recall_at_5": 0.0, "precision_at_5": 0.0, "mrr": 0.0}

    count = len(results)
    return {
        "count": count,
        "recall_at_1": sum(r.recall_at_k.get(1, 0.0) for r in results) / count,
        "recall_at_3": sum(r.recall_at_k.get(3, 0.0) for r in results) / count,
        "recall_at_5": sum(r.recall_at_k.get(5, 0.0) for r in results) / count,
        "precision_at_5": sum(r.precision_at_5 for r in results) / count,
        "mrr": sum(r.mrr for r in results) / count,
    }
