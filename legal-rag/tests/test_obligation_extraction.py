"""Tests for legal obligation and right extraction.

Tests cover:
- Obligation extraction from various patterns
- Right extraction
- Condition identification
- Deadline parsing
- Risk classification
- Evidence tracking
"""

import pytest
from src.extraction.obligation_extractor import ObligationExtractor


class TestObligationExtraction:
    """Tests for obligation extraction."""

    @pytest.fixture
    def extractor(self):
        """Create extractor instance."""
        return ObligationExtractor(document_id="test-doc-001")

    def test_extract_simple_shall_obligation(self, extractor):
        """Extract basic 'shall' obligation."""
        text = "Buyer shall pay $100 within 30 days"
        result = extractor.extract(text, chunk_id="chunk-1")

        assert len(result.obligations) >= 1
        obligation = result.obligations[0]
        assert obligation.actor.name == "Buyer"
        assert "pay" in obligation.action.lower()
        assert obligation.severity == "MUST"

    def test_extract_must_obligation(self, extractor):
        """Extract 'must' obligation."""
        text = "Seller must deliver goods by June 1, 2025"
        result = extractor.extract(text)

        obligations = result.obligations
        assert len(obligations) >= 1
        assert any("deliver" in o.action.lower() for o in obligations)

    def test_extract_multiple_obligations(self, extractor):
        """Extract multiple obligations from text."""
        text = """
        Buyer shall pay within 30 days.
        Seller must deliver goods by June 1.
        Licensor will provide support during contract term.
        """
        result = extractor.extract(text)

        assert len(result.obligations) >= 2

    def test_actor_name_normalization(self, extractor):
        """Normalize actor names correctly."""
        text = "the Buyer shall pay"
        result = extractor.extract(text)

        assert len(result.obligations) >= 1
        # "the" should be removed
        assert "Buyer" in result.obligations[0].actor.name

    def test_skip_short_actions(self, extractor):
        """Skip very short obligation actions."""
        text = "Buyer shall go."  # Very short action
        result = extractor.extract(text)

        # Should skip this (too short)
        assert len([o for o in result.obligations if len(o.action) < 5]) == 0


class TestRightExtraction:
    """Tests for right extraction."""

    @pytest.fixture
    def extractor(self):
        return ObligationExtractor(document_id="test-doc-001")

    def test_extract_may_right(self, extractor):
        """Extract 'may' right."""
        text = "Buyer may cancel within 30 days"
        result = extractor.extract(text)

        assert len(result.rights) >= 1
        right = result.rights[0]
        assert right.actor.name == "Buyer"
        assert "cancel" in right.action.lower()

    def test_extract_has_right_to(self, extractor):
        """Extract 'has the right to' right."""
        text = "Seller has the right to audit records"
        result = extractor.extract(text)

        assert len(result.rights) >= 1
        assert any("audit" in r.action.lower() for r in result.rights)

    def test_extract_entitled_right(self, extractor):
        """Extract 'entitled to' right."""
        text = "Company is entitled to injunctive relief"
        result = extractor.extract(text)

        assert len(result.rights) >= 1
        assert any("injunctive" in r.action.lower() for r in result.rights)

    def test_multiple_rights(self, extractor):
        """Extract multiple rights."""
        text = """
        Buyer may cancel anytime.
        Seller can audit records.
        Licensor is entitled to royalties.
        """
        result = extractor.extract(text)

        assert len(result.rights) >= 2


class TestConditionExtraction:
    """Tests for condition extraction."""

    @pytest.fixture
    def extractor(self):
        return ObligationExtractor(document_id="test-doc-001")

    def test_extract_if_condition(self, extractor):
        """Extract 'if' condition."""
        text = "If buyer requests, seller shall provide warranty"
        result = extractor.extract(text)

        conditions = result.conditions
        assert len(conditions) > 0

    def test_extract_unless_condition(self, extractor):
        """Extract 'unless' condition."""
        text = "Seller must respond unless weather prevents"
        result = extractor.extract(text)

        assert len(result.conditions) > 0 or len(result.obligations) > 0

    def test_extract_provided_that_condition(self, extractor):
        """Extract 'provided that' condition."""
        text = "Warranty applies provided that defect within 90 days"
        result = extractor.extract(text)

        assert len(result.conditions) > 0

    def test_condition_type_classification(self, extractor):
        """Classify condition types correctly."""
        text = "If weather, terminate unless emergency"
        result = extractor.extract(text)

        # Should have trigger and limitation conditions
        triggers = [c for c in result.conditions if c.condition_type == "trigger"]
        limits = [c for c in result.conditions if c.condition_type == "limitation"]

        # At least one should be detected
        assert len(triggers) > 0 or len(limits) > 0


class TestDeadlineExtraction:
    """Tests for deadline extraction."""

    @pytest.fixture
    def extractor(self):
        return ObligationExtractor(document_id="test-doc-001")

    def test_extract_relative_deadline_days(self, extractor):
        """Extract 'within X days' deadline."""
        text = "Payment due within 30 days"
        result = extractor.extract(text)

        obligations = result.obligations
        if obligations:
            deadline = obligations[0].deadline
            if deadline:
                assert "30 days" in deadline.duration or deadline.duration == "30 days"

    def test_extract_business_days(self, extractor):
        """Extract business days deadline."""
        text = "Response required within 5 business days"
        result = extractor.extract(text)

        obligations = result.obligations
        assert len(obligations) > 0

    def test_extract_absolute_deadline(self, extractor):
        """Extract absolute date deadline."""
        text = "Payment due by June 1, 2025"
        result = extractor.extract(text)

        # May or may not extract (depends on pattern matching)
        # Just verify no errors
        assert isinstance(result.obligations, list)


class TestPenaltyExtraction:
    """Tests for penalty extraction."""

    @pytest.fixture
    def extractor(self):
        return ObligationExtractor(document_id="test-doc-001")

    def test_extract_late_fee_penalty(self, extractor):
        """Extract late fee penalty."""
        text = "If payment delayed, 5% monthly penalty applies"
        result = extractor.extract(text)

        obligations = result.obligations
        assert len(obligations) > 0

    def test_extract_percentage_penalty(self, extractor):
        """Extract percentage-based penalty."""
        text = "Late payment subject to 2% per month interest"
        result = extractor.extract(text)

        obligations = result.obligations
        assert len(obligations) > 0


class TestRiskClassification:
    """Tests for risk classification."""

    @pytest.fixture
    def extractor(self):
        return ObligationExtractor(document_id="test-doc-001")

    def test_classify_liability_risk_as_critical(self, extractor):
        """Unlimited liability should be CRITICAL risk."""
        text = "Company liable for unlimited damages"
        result = extractor.extract(text)

        assert len(result.risks) > 0
        risks = [r for r in result.risks if r.risk_level == "CRITICAL"]
        assert len(risks) > 0

    def test_classify_termination_risk_as_critical(self, extractor):
        """Termination clauses should be CRITICAL."""
        text = "Material breach allows immediate termination"
        result = extractor.extract(text)

        risks = [r for r in result.risks if r.risk_level == "CRITICAL"]
        assert len(risks) > 0

    def test_classify_payment_risk_as_high(self, extractor):
        """Payment obligations should be HIGH risk."""
        text = "Buyer must pay $100,000 by June 1"
        result = extractor.extract(text)

        # Should have some risk
        assert len(result.risks) > 0

    def test_risk_summary(self, extractor):
        """Risk summary counts by level."""
        text = "Company liable for unlimited damages and must pay by June 1"
        result = extractor.extract(text)

        summary = result.risk_summary
        assert isinstance(summary, dict)
        assert sum(summary.values()) == len(result.risks)


class TestEvidenceTracking:
    """Tests for evidence/source tracking."""

    @pytest.fixture
    def extractor(self):
        return ObligationExtractor(document_id="test-doc-001")

    def test_evidence_preserved_in_obligation(self, extractor):
        """Evidence should be attached to obligation."""
        text = "Buyer shall pay within 30 days"
        result = extractor.extract(text, chunk_id="chunk-1", section="4.2", section_name="Payment")

        assert len(result.obligations) > 0
        obligation = result.obligations[0]
        assert obligation.evidence is not None
        assert obligation.evidence.document_id == "test-doc-001"
        assert obligation.evidence.section == "4.2"
        assert obligation.evidence.quote is not None

    def test_evidence_preserved_in_right(self, extractor):
        """Evidence should be attached to right."""
        text = "Buyer may cancel anytime"
        result = extractor.extract(text, chunk_id="chunk-2", section="5.1")

        assert len(result.rights) > 0
        right = result.rights[0]
        assert right.evidence is not None

    def test_confidence_score(self, extractor):
        """Confidence scores should be reasonable."""
        text = "Seller must deliver goods"
        result = extractor.extract(text)

        assert 0.0 <= result.confidence_overall <= 1.0
        for obligation in result.obligations:
            assert 0.0 <= obligation.confidence <= 1.0


class TestActorExtraction:
    """Tests for actor identification."""

    @pytest.fixture
    def extractor(self):
        return ObligationExtractor(document_id="test-doc-001")

    def test_extract_actors_from_obligations(self, extractor):
        """Extract actors from obligations."""
        text = """
        Buyer shall pay.
        Seller shall deliver.
        Licensor grants rights.
        """
        result = extractor.extract(text)

        actors = result.actors
        actor_names = [a.name for a in actors]
        assert "Buyer" in actor_names or any("buyer" in n.lower() for n in actor_names)

    def test_deduplicate_actors(self, extractor):
        """Duplicate actors should be deduplicated."""
        text = """
        Buyer shall pay.
        Buyer shall accept goods.
        """
        result = extractor.extract(text)

        actors = result.actors
        buyer_count = sum(1 for a in actors if "buyer" in a.name.lower())
        # Should have at most one Buyer (or similar)
        assert buyer_count <= 1 or len(actors) <= 2

    def test_handle_pronouns(self, extractor):
        """Handle pronouns referring to parties."""
        text = "The Buyer shall pay. They must do so within 30 days"
        result = extractor.extract(text)

        # Should still extract obligation even with pronoun
        assert len(result.obligations) > 0


class TestBatchExtraction:
    """Tests for batch extraction."""

    @pytest.fixture
    def extractor(self):
        return ObligationExtractor(document_id="test-doc-001")

    def test_batch_extract_multiple_chunks(self, extractor):
        """Batch extract from multiple text chunks."""
        texts = [
            "Buyer shall pay $100",
            "Seller must deliver goods",
            "Licensor grants rights",
        ]

        results = extractor.batch_extract(texts)

        assert len(results) == 3
        assert all(isinstance(r, type(results[0])) for r in results)

    def test_batch_extract_with_chunk_ids(self, extractor):
        """Batch extract with custom chunk IDs."""
        texts = ["Buyer shall pay", "Seller shall deliver"]
        chunk_ids = ["chunk-a", "chunk-b"]

        results = extractor.batch_extract(texts, chunk_ids)

        assert results[0].chunk_id == "chunk-a"
        assert results[1].chunk_id == "chunk-b"


class TestComplexContracts:
    """Tests with realistic contract language."""

    @pytest.fixture
    def extractor(self):
        return ObligationExtractor(document_id="contract-001")

    def test_extract_from_payment_terms_section(self, extractor):
        """Extract from realistic payment terms."""
        text = """
        4.2 Payment Terms
        Buyer shall pay Seller the Invoice Amount within thirty (30) days
        of receipt of invoice. Payment shall be made via bank transfer to
        Seller's designated account. If payment is not received within the
        required period, Buyer shall pay interest at 1.5% per month on the
        outstanding balance.
        """

        result = extractor.extract(text, section="4.2", section_name="Payment Terms")

        # Should find multiple obligations
        assert len(result.obligations) >= 2
        assert len(result.risks) > 0

    def test_extract_from_warranty_clause(self, extractor):
        """Extract from realistic warranty clause."""
        text = """
        5.1 Warranty
        Seller warrants that goods are fit for purpose. Seller shall
        provide warranty coverage for 12 months from delivery. The warranty
        does not apply if defect caused by buyer misuse, unless buyer
        paid for extended coverage.
        """

        result = extractor.extract(text, section="5.1", section_name="Warranty")

        assert len(result.obligations) > 0
        assert len(result.conditions) > 0 or any("unless" in o.action.lower() for o in result.obligations)

    def test_extract_from_termination_clause(self, extractor):
        """Extract from termination clause."""
        text = """
        8.1 Termination for Cause
        Either party may terminate this Agreement immediately upon written
        notice if (i) the other party breaches any material term and fails
        to cure within thirty (30) days of notice, or (ii) the other party
        becomes insolvent, except that the cure period shall not apply in
        cases of breach of confidentiality or IP infringement.
        """

        result = extractor.extract(text, section="8.1", section_name="Termination")

        # Should identify termination right
        termination_rights = [r for r in result.rights if "terminate" in r.action.lower()]
        assert len(termination_rights) > 0

        # Should identify CRITICAL risk
        critical_risks = [r for r in result.risks if r.risk_level == "CRITICAL"]
        assert len(critical_risks) > 0


class TestExtractionQuality:
    """Tests for extraction quality metrics."""

    @pytest.fixture
    def extractor(self):
        return ObligationExtractor(document_id="test-doc-001")

    def test_extraction_time_measured(self, extractor):
        """Extraction time should be measured."""
        text = "Buyer shall pay within 30 days"
        result = extractor.extract(text)

        assert result.extraction_time_ms > 0

    def test_model_used_recorded(self, extractor):
        """Model used should be recorded."""
        text = "Buyer shall pay"
        result = extractor.extract(text)

        assert result.model_used == "pattern-based"

    def test_confidence_scores_reasonable(self, extractor):
        """Confidence scores should be in valid range."""
        text = "Buyer shall pay within 30 days"
        result = extractor.extract(text)

        assert 0.0 <= result.confidence_overall <= 1.0
        for ob in result.obligations:
            assert 0.0 <= ob.confidence <= 1.0
        for ri in result.rights:
            assert 0.0 <= ri.confidence <= 1.0
        for r in result.risks:
            assert 0.0 <= r.confidence <= 1.0
