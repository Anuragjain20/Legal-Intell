"""Tests for query analysis and normalization."""

from __future__ import annotations

import pytest

from src.query.analyzer import QueryAnalyzer
from src.query.models import NormalizedQuery, QueryIntent


class TestQueryAnalyzerBasics:
    """Tests for basic query analysis."""

    def test_analyzer_rejects_blank_query(self):
        analyzer = QueryAnalyzer()
        with pytest.raises(ValueError):
            analyzer.analyze("")

    def test_analyzer_rejects_whitespace_only_query(self):
        analyzer = QueryAnalyzer()
        with pytest.raises(ValueError):
            analyzer.analyze("   ")

    def test_analyzer_preserves_original_query(self):
        analyzer = QueryAnalyzer()
        original = "What are the termination conditions?"
        result = analyzer.analyze(original)
        assert result.original == original

    def test_analyzer_normalizes_whitespace(self):
        analyzer = QueryAnalyzer()
        result = analyzer.analyze("What   are   the   termination    conditions?")
        assert result.normalized == "What are the termination conditions?"

    def test_analyzer_sets_query_length(self):
        analyzer = QueryAnalyzer()
        result = analyzer.analyze("What are the termination conditions?")
        assert result.query_length == 6  # 6 words


class TestQueryIntentDetection:
    """Tests for query intent detection."""

    def test_detect_obligation_intent(self):
        analyzer = QueryAnalyzer()
        result = analyzer.analyze("What must the party do under this agreement?")
        assert result.intent == QueryIntent.OBLIGATION

    def test_detect_definition_intent(self):
        analyzer = QueryAnalyzer()
        result = analyzer.analyze("What does 'material breach' mean?")
        assert result.intent == QueryIntent.DEFINITION

    def test_detect_right_intent(self):
        analyzer = QueryAnalyzer()
        result = analyzer.analyze("What rights does the licensor have?")
        assert result.intent == QueryIntent.RIGHT

    def test_detect_condition_intent(self):
        analyzer = QueryAnalyzer()
        result = analyzer.analyze("What conditions must be met for termination?")
        assert result.intent == QueryIntent.CONDITION

    def test_detect_procedure_intent(self):
        analyzer = QueryAnalyzer()
        result = analyzer.analyze("How should the notice be delivered?")
        assert result.intent == QueryIntent.PROCEDURE

    def test_detect_scope_intent(self):
        analyzer = QueryAnalyzer()
        result = analyzer.analyze("To which parties does this clause apply?")
        assert result.intent == QueryIntent.SCOPE

    def test_detect_temporal_intent(self):
        analyzer = QueryAnalyzer()
        result = analyzer.analyze("When does the agreement become effective?")
        assert result.intent == QueryIntent.TEMPORAL

    def test_detect_general_inquiry_fallback(self):
        analyzer = QueryAnalyzer()
        result = analyzer.analyze("Tell me about the contract.")
        assert result.intent == QueryIntent.GENERAL_INQUIRY


class TestLegalTermExtraction:
    """Tests for legal term detection."""

    def test_extract_obligation_terms(self):
        analyzer = QueryAnalyzer()
        result = analyzer.analyze("The party shall provide written notice.")
        assert len(result.legal_terms) > 0
        assert any(term.term == "shall" for term in result.legal_terms)

    def test_extract_multiple_legal_terms(self):
        analyzer = QueryAnalyzer()
        result = analyzer.analyze("The party must perform its obligations under this agreement.")
        assert len(result.legal_terms) >= 2
        terms = {term.term for term in result.legal_terms}
        assert "must" in terms
        assert "obligation" in terms

    def test_extract_definition_term(self):
        analyzer = QueryAnalyzer()
        result = analyzer.analyze("'Material breach' means failure to perform.")
        assert len(result.legal_terms) > 0
        assert any(term.term == "means" for term in result.legal_terms)

    def test_legal_term_confidence(self):
        analyzer = QueryAnalyzer()
        result = analyzer.analyze("What are the termination conditions?")
        for term in result.legal_terms:
            assert 0.0 <= term.confidence <= 1.0
            assert term.confidence > 0.5  # Should be fairly confident


class TestExactQuotedTerms:
    """Tests for exact quoted term extraction."""

    def test_extract_single_quoted_term(self):
        analyzer = QueryAnalyzer()
        result = analyzer.analyze('What is "material breach"?')
        assert len(result.exact_matches) == 1
        assert result.exact_matches[0] == "material breach"

    def test_extract_multiple_quoted_terms(self):
        analyzer = QueryAnalyzer()
        result = analyzer.analyze('Define "consideration" and "valuable".')
        assert len(result.exact_matches) == 2
        assert "consideration" in result.exact_matches
        assert "valuable" in result.exact_matches

    def test_no_quoted_terms(self):
        analyzer = QueryAnalyzer()
        result = analyzer.analyze("What are the termination conditions?")
        assert len(result.exact_matches) == 0

    def test_preserve_quoted_term_case(self):
        analyzer = QueryAnalyzer()
        result = analyzer.analyze('What is "Material Breach"?')
        assert "Material Breach" in result.exact_matches


class TestNegationDetection:
    """Tests for negation detection."""

    def test_detect_not_negation(self):
        analyzer = QueryAnalyzer()
        result = analyzer.analyze("The party must not disclose confidential information.")
        assert result.has_negation is True

    def test_detect_no_negation(self):
        analyzer = QueryAnalyzer()
        result = analyzer.analyze("No party can transfer its rights.")
        assert result.has_negation is True

    def test_detect_cannot_negation(self):
        analyzer = QueryAnalyzer()
        result = analyzer.analyze("The licensor cannot modify the license.")
        assert result.has_negation is True

    def test_no_negation_present(self):
        analyzer = QueryAnalyzer()
        result = analyzer.analyze("What are the termination conditions?")
        assert result.has_negation is False


class TestTemporalConstraintDetection:
    """Tests for temporal constraint detection."""

    def test_detect_when_temporal(self):
        analyzer = QueryAnalyzer()
        result = analyzer.analyze("When does the agreement terminate?")
        assert result.has_temporal_constraint is True

    def test_detect_date_temporal(self):
        analyzer = QueryAnalyzer()
        result = analyzer.analyze("What is the effective date?")
        assert result.has_temporal_constraint is True

    def test_detect_period_temporal(self):
        analyzer = QueryAnalyzer()
        result = analyzer.analyze("What is the notice period?")
        assert result.has_temporal_constraint is True

    def test_no_temporal_constraint(self):
        analyzer = QueryAnalyzer()
        result = analyzer.analyze("What are the termination conditions?")
        assert result.has_temporal_constraint is False


class TestRetrievalSignals:
    """Tests for retrieval signal extraction."""

    def test_legal_terms_become_signals(self):
        analyzer = QueryAnalyzer()
        result = analyzer.analyze("What must the party do?")
        assert len(result.retrieval_signals) > 0
        assert any(sig.signal == "must" for sig in result.retrieval_signals)
        assert any(sig.category == "legal_term" for sig in result.retrieval_signals)

    def test_signal_weights_are_valid(self):
        analyzer = QueryAnalyzer()
        result = analyzer.analyze("What must the party do under the agreement?")
        for signal in result.retrieval_signals:
            assert 0.0 <= signal.weight <= 1.0

    def test_high_confidence_legal_terms(self):
        analyzer = QueryAnalyzer()
        result = analyzer.analyze("The party shall comply.")
        legal_signals = [s for s in result.retrieval_signals if s.category == "legal_term"]
        assert all(s.weight >= 0.85 for s in legal_signals)


class TestProcessingPerformance:
    """Tests for query processing latency."""

    def test_processing_time_is_measured(self):
        analyzer = QueryAnalyzer()
        result = analyzer.analyze("What are the termination conditions?")
        assert result.processing_time_ms >= 0
        assert result.processing_time_ms < 100  # Should be fast

    def test_complex_query_processing_time(self):
        analyzer = QueryAnalyzer()
        long_query = (
            "What happens if either party terminates the agreement because of a material breach, "
            "and what notice must be provided within how many days?"
        )
        result = analyzer.analyze(long_query)
        assert result.processing_time_ms < 500  # Should still be reasonably fast


class TestComplexQueries:
    """Tests for realistic complex legal queries."""

    def test_analyze_termination_query(self):
        analyzer = QueryAnalyzer()
        query = "What happens if either party terminates the agreement because of a material breach?"
        result = analyzer.analyze(query)

        assert result.original == query
        assert result.intent in {QueryIntent.CONDITION, QueryIntent.OBLIGATION, QueryIntent.PROCEDURE}
        assert len(result.legal_terms) > 0
        assert result.has_temporal_constraint is True

    def test_analyze_definition_query(self):
        analyzer = QueryAnalyzer()
        query = 'What is the definition of "material breach" under Section 2(a)?'
        result = analyzer.analyze(query)

        assert result.intent == QueryIntent.DEFINITION
        assert "material breach" in result.exact_matches
        assert len(result.legal_terms) > 0

    def test_analyze_obligation_with_negation(self):
        analyzer = QueryAnalyzer()
        query = "Which party cannot disclose confidential information without prior written consent?"
        result = analyzer.analyze(query)

        assert result.has_negation is True
        assert result.intent in {QueryIntent.OBLIGATION, QueryIntent.RIGHT}

    def test_analyze_scope_query(self):
        analyzer = QueryAnalyzer()
        query = "To which documents does Section 5 apply?"
        result = analyzer.analyze(query)

        assert result.intent in {QueryIntent.SCOPE, QueryIntent.GENERAL_INQUIRY}
        assert len(result.legal_terms) > 0

    def test_analyze_multiple_queries(self):
        analyzer = QueryAnalyzer()
        queries = [
            "What are the termination conditions?",
            "How long is the notice period?",
            "Define 'material breach'.",
            "Who can terminate the agreement?",
            "When does the agreement become effective?",
        ]

        for query in queries:
            result = analyzer.analyze(query)
            assert result.original == query
            assert result.query_length > 0
            assert result.intent != QueryIntent.GENERAL_INQUIRY or query != queries[0]


class TestNormalizedQueryImmutability:
    """Tests for NormalizedQuery immutability and frozen state."""

    def test_normalized_query_is_frozen(self):
        analyzer = QueryAnalyzer()
        result = analyzer.analyze("What are the termination conditions?")
        with pytest.raises(AttributeError):
            result.original = "Modified"

    def test_legal_terms_list_is_immutable(self):
        analyzer = QueryAnalyzer()
        result = analyzer.analyze("The party must perform.")
        # The list itself is mutable but the dataclass is frozen
        with pytest.raises(AttributeError):
            result.legal_terms = []
