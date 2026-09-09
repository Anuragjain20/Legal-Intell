"""Generation-faithfulness evaluation harness.

Retrieval evaluation (harness.py) only checks whether the right chunk was
found - it says nothing about whether the LLM's answer is actually
faithful to what was retrieved. This harness runs the full pipeline
(retrieval -> generation -> citation mapping) for each in-corpus question
and checks, without an LLM judge:

1. Groundedness: did the answer resolve at least one citation, rather than
   either declining to answer or citing sources that don't exist in the
   context it was given (CitationMapper already tracks this - see
   src/generation/citations.py)?
2. Citation faithfulness: does at least one of the sources the model
   actually cited contain the dataset's expected_answer_span? This checks
   whether the model grounded its answer in evidence that really supports
   it, using the same verbatim-span ground truth as the retrieval harness
   (src/evaluation/matching.py) - not whether the answer text itself is a
   perfect paraphrase, which would need a judge model this harness
   deliberately avoids.
3. Unresolved-citation rate: how often the model referenced a source
   number that didn't resolve to real context (a direct hallucination
   signal already computed by CitationMapper, just aggregated here).

Out-of-corpus (is_out_of_corpus) questions are scored separately: a
"pass" is the pipeline correctly declining to answer (either the
retriever's confidence gate refuses, or the LLM says it found nothing),
not the answer's content.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from src.evaluation.matching import DOCUMENT_SEPARATOR, span_matches, split_multi_span
from src.generation.exceptions import GenerationError
from src.retrieval.exceptions import NoRelevantResultsError


@dataclass
class GenerationCaseResult:
    """Per-question generation evaluation outcome."""

    case_id: str
    question_type: str
    is_out_of_corpus: bool
    refused: bool = False
    insufficient_evidence: bool = False
    error: str | None = None
    citations_resolved: int = 0
    citations_unresolved: int = 0
    cited_span_faithful: bool | None = None  # None when not applicable (no expected span, or no citations)


@dataclass
class GenerationEvaluationSummary:
    """Aggregate generation-quality metrics."""

    total_cases: int
    in_corpus_cases: int
    unanswerable_cases: int
    groundedness_rate: float  # in-corpus cases with >=1 resolved citation and no error
    citation_faithfulness_rate: float  # among cases with a faithfulness verdict, fraction True
    unresolved_citation_rate: float  # unresolved / (resolved + unresolved), across in-corpus cases
    unanswerable_refusal_rate: float  # out-of-corpus cases where the pipeline declined to answer
    case_results: list[GenerationCaseResult]


def load_dataset(dataset_path: Path) -> dict:
    return json.loads(dataset_path.read_text(encoding="utf-8"))


def _looks_like_no_answer(answer: str) -> bool:
    return "could not find this information" in answer.lower()


def evaluate_generation_case(retriever, generation_service, case: dict, top_k: int = 5) -> GenerationCaseResult:
    result = GenerationCaseResult(
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

    try:
        generation = generation_service.answer(case["question"], retrieved)
    except GenerationError as exc:
        result.error = f"{type(exc).__name__}: {exc}"
        return result

    result.insufficient_evidence = generation.insufficient_evidence
    result.citations_resolved = len(generation.citations or [])
    result.citations_unresolved = len(generation.unresolved_source_ids or [])

    if result.is_out_of_corpus:
        result.refused = generation.insufficient_evidence or _looks_like_no_answer(generation.answer)
        return result

    if not generation.citations:
        return result

    documents = case["expected_document"].split(DOCUMENT_SEPARATOR)
    spans = split_multi_span(case["expected_answer_span"])
    if len(documents) == 1 and len(spans) > 1:
        documents = documents * len(spans)

    cited_chunk_ids = {c.chunk_id for c in generation.citations}
    cited_sources = [s for s in generation.used_context.sources if s.chunk_id in cited_chunk_ids]

    faithful = False
    for source in cited_sources:
        for doc_name, span in zip(documents, spans):
            if source.document_name == doc_name and span_matches(span, source.text):
                faithful = True
                break
        if faithful:
            break
    result.cited_span_faithful = faithful

    return result


def run_generation_evaluation(retriever, generation_service, dataset: dict, top_k: int = 5) -> GenerationEvaluationSummary:
    all_results = [
        evaluate_generation_case(retriever, generation_service, case, top_k=top_k) for case in dataset["questions"]
    ]

    in_corpus = [r for r in all_results if not r.is_out_of_corpus]
    unanswerable = [r for r in all_results if r.is_out_of_corpus]

    grounded = [r for r in in_corpus if r.error is None and not r.refused and r.citations_resolved > 0]
    groundedness_rate = len(grounded) / len(in_corpus) if in_corpus else 0.0

    faithfulness_verdicts = [r.cited_span_faithful for r in in_corpus if r.cited_span_faithful is not None]
    faithfulness_rate = sum(faithfulness_verdicts) / len(faithfulness_verdicts) if faithfulness_verdicts else 0.0

    total_resolved = sum(r.citations_resolved for r in in_corpus)
    total_unresolved = sum(r.citations_unresolved for r in in_corpus)
    unresolved_rate = total_unresolved / (total_resolved + total_unresolved) if (total_resolved + total_unresolved) else 0.0

    refused_count = sum(1 for r in unanswerable if r.refused)
    refusal_rate = refused_count / len(unanswerable) if unanswerable else 0.0

    return GenerationEvaluationSummary(
        total_cases=len(all_results),
        in_corpus_cases=len(in_corpus),
        unanswerable_cases=len(unanswerable),
        groundedness_rate=groundedness_rate,
        citation_faithfulness_rate=faithfulness_rate,
        unresolved_citation_rate=unresolved_rate,
        unanswerable_refusal_rate=refusal_rate,
        case_results=all_results,
    )
