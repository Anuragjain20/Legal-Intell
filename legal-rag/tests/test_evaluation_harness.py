"""Regression tests for src/evaluation/harness.py's relevant-chunk scoring.

Covers a real bug found while checking the eval dataset's multi-span
questions: _find_relevant_chunk_ids used to only ever consider chunks that
were actually retrieved, so relevant_chunk_ids was always a subset of
retrieved_chunk_ids by construction - Recall@K's denominator could never
exceed its numerator, silently reporting 1.0 recall on a question where only
one of two true relevant chunks was found. The fix scores against the full
chunk universe (build_relevant_chunk_index / chunks_by_document), scanned
once per run from vector_store.get_all(), the same way
scripts/validate_dataset.py already checks span-findability.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.evaluation.harness import build_relevant_chunk_index, evaluate_case, run_evaluation
from src.retrieval.exceptions import NoRelevantResultsError


@dataclass(frozen=True)
class _RecordView:
    chunk_id: str
    document_name: str | None
    text: str


@dataclass(frozen=True)
class _ScoredChunk:
    score: float
    record: _RecordView


class _FakeVectorRecord:
    def __init__(self, chunk_id, document_name, text):
        self.chunk_id = chunk_id
        self.document_name = document_name
        self.text = text


class _FakeVectorStore:
    def __init__(self, records):
        self._records = records

    def get_all(self):
        return self._records


class _FixedResultRetriever:
    """Always returns the same chunk_ids/texts, regardless of question."""

    def __init__(self, chunks: list[_ScoredChunk], refuse: bool = False):
        self._chunks = chunks
        self._refuse = refuse

    def retrieve(self, question, top_k=5):
        if self._refuse:
            raise NoRelevantResultsError("no results")
        return self._chunks[:top_k]


def _chunks_index(records: list[_FakeVectorRecord]) -> dict[str, list[tuple[str, str]]]:
    return build_relevant_chunk_index(_FakeVectorStore(records))


class TestFullCorpusRelevantChunkScoring:
    def test_partial_multi_span_hit_reports_recall_below_one(self):
        """Two true relevant chunks exist for this question; only one is
        retrieved. Recall@5 must reflect that miss, not report 1.0."""
        all_chunks = [
            _FakeVectorRecord("doc:0001", "contract.pdf", "The first relevant span appears here."),
            _FakeVectorRecord("doc:0002", "contract.pdf", "The second relevant span appears here."),
            _FakeVectorRecord("doc:0003", "contract.pdf", "Unrelated filler text."),
        ]
        chunks_by_document = _chunks_index(all_chunks)

        # Retriever only found the first of the two relevant chunks.
        retrieved = [_ScoredChunk(score=0.9, record=_RecordView("doc:0001", "contract.pdf", all_chunks[0].text))]
        retriever = _FixedResultRetriever(retrieved)

        case = {
            "id": "Q_test",
            "question_type": "multi_section",
            "question": "irrelevant for this test",
            "expected_document": "contract.pdf",
            "expected_answer_span": "The first relevant span appears here. ||| The second relevant span appears here.",
        }

        result = evaluate_case(retriever, case, chunks_by_document, top_k=5)

        assert len(result.relevant_chunk_ids) == 2  # true universe, not just what was retrieved
        assert result.recall_at_k[5] == 0.5  # found 1 of 2, not 1.0

    def test_full_multi_span_hit_reports_recall_one(self):
        all_chunks = [
            _FakeVectorRecord("doc:0001", "contract.pdf", "The first relevant span appears here."),
            _FakeVectorRecord("doc:0002", "contract.pdf", "The second relevant span appears here."),
        ]
        chunks_by_document = _chunks_index(all_chunks)
        retrieved = [
            _ScoredChunk(score=0.9, record=_RecordView("doc:0001", "contract.pdf", all_chunks[0].text)),
            _ScoredChunk(score=0.8, record=_RecordView("doc:0002", "contract.pdf", all_chunks[1].text)),
        ]
        retriever = _FixedResultRetriever(retrieved)

        case = {
            "id": "Q_test",
            "question_type": "multi_section",
            "question": "irrelevant",
            "expected_document": "contract.pdf",
            "expected_answer_span": "The first relevant span appears here. ||| The second relevant span appears here.",
        }

        result = evaluate_case(retriever, case, chunks_by_document, top_k=5)

        assert len(result.relevant_chunk_ids) == 2
        assert result.recall_at_k[5] == 1.0

    def test_single_span_question_unaffected(self):
        all_chunks = [_FakeVectorRecord("doc:0001", "contract.pdf", "The only relevant span.")]
        chunks_by_document = _chunks_index(all_chunks)
        retrieved = [_ScoredChunk(score=0.9, record=_RecordView("doc:0001", "contract.pdf", all_chunks[0].text))]
        retriever = _FixedResultRetriever(retrieved)

        case = {
            "id": "Q_test",
            "question_type": "direct_factual",
            "question": "irrelevant",
            "expected_document": "contract.pdf",
            "expected_answer_span": "The only relevant span.",
        }

        result = evaluate_case(retriever, case, chunks_by_document, top_k=5)

        assert len(result.relevant_chunk_ids) == 1
        assert result.recall_at_k[5] == 1.0

    def test_relevant_chunk_index_scans_whole_corpus_not_just_retrieved(self):
        """build_relevant_chunk_index must include chunks the retriever
        never returns - it's the full ground-truth universe."""
        all_chunks = [
            _FakeVectorRecord("doc:0001", "contract.pdf", "Alpha span."),
            _FakeVectorRecord("doc:0002", "contract.pdf", "Beta span."),
            _FakeVectorRecord("doc:0003", "other.pdf", "Gamma span."),
        ]
        index = build_relevant_chunk_index(_FakeVectorStore(all_chunks))

        assert set(index) == {"contract.pdf", "other.pdf"}
        assert len(index["contract.pdf"]) == 2
        assert len(index["other.pdf"]) == 1


class TestRunEvaluationThreadsChunkIndexThrough:
    def test_run_evaluation_accepts_chunks_by_document(self):
        all_chunks = [
            _FakeVectorRecord("doc:0001", "contract.pdf", "The first relevant span appears here."),
            _FakeVectorRecord("doc:0002", "contract.pdf", "The second relevant span appears here."),
        ]
        chunks_by_document = _chunks_index(all_chunks)
        retrieved = [_ScoredChunk(score=0.9, record=_RecordView("doc:0001", "contract.pdf", all_chunks[0].text))]
        retriever = _FixedResultRetriever(retrieved)

        dataset = {
            "questions": [
                {
                    "id": "Q1",
                    "question_type": "multi_section",
                    "question": "irrelevant",
                    "expected_document": "contract.pdf",
                    "expected_answer_span": "The first relevant span appears here. ||| The second relevant span appears here.",
                }
            ]
        }

        summary = run_evaluation(retriever, dataset, similarity_threshold=None, chunks_by_document=chunks_by_document)

        assert summary.case_results[0].recall_at_k[5] == 0.5
