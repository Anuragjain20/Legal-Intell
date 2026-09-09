"""Pattern-based legal obligation and right extraction.

Extracts obligations, rights, conditions, deadlines, and risks from legal text.
"""

from __future__ import annotations

import re
import time
import uuid
from typing import Optional

from src.extraction.models import (
    Actor,
    Condition,
    ConditionType,
    Deadline,
    DeadlineType,
    Evidence,
    ExtractionResult,
    Obligation,
    Right,
    Risk,
    RiskCategory,
    RiskLevel,
    SeverityLevel,
)
from src.extraction.patterns import (
    ConditionPatterns,
    DeadlinePatterns,
    ObligationPatterns,
    PenaltyPatterns,
    RightPatterns,
    extract_text_around_match,
    find_line_number,
    normalize_actor_name,
)


class ObligationExtractor:
    """Extract obligations, rights, and conditions from legal text.

    Pattern-based extraction using regex patterns for high recall,
    can be combined with LLM for higher precision.
    """

    def __init__(
        self,
        document_id: str,
        model_used: str = "pattern-based",
        min_confidence: float = 0.5,
    ):
        """Initialize extractor.

        Args:
            document_id: ID of document being processed
            model_used: Name of extraction model
            min_confidence: Minimum confidence to include result
        """
        self.document_id = document_id
        self.model_used = model_used
        self.min_confidence = min_confidence

    def extract(
        self,
        text: str,
        chunk_id: str = None,
        section: str = None,
        section_name: str = None,
        page_number: int = 1,
    ) -> ExtractionResult:
        """Extract all obligations, rights, and risks from text.

        Args:
            text: Legal text to extract from
            chunk_id: ID of text chunk
            section: Section number
            section_name: Section title
            page_number: Page number in document

        Returns:
            ExtractionResult with all extracted items
        """
        start_time = time.time()

        chunk_id = chunk_id or str(uuid.uuid4())[:8]
        section = section or "unknown"
        section_name = section_name or "Unknown Section"

        # Extract each type
        obligations = self._extract_obligations(text, chunk_id, section, section_name, page_number)
        rights = self._extract_rights(text, chunk_id, section, section_name, page_number)
        conditions = self._extract_conditions(text, chunk_id)

        # Classify risks
        risks = self._classify_risks(obligations + rights, chunk_id)

        # Calculate overall confidence
        if obligations or rights:
            confidence = sum(
                item.confidence for item in [*obligations, *rights]
            ) / max(len(obligations) + len(rights), 1)
        else:
            confidence = 0.7  # Low confidence if nothing found

        elapsed = (time.time() - start_time) * 1000

        return ExtractionResult(
            chunk_id=chunk_id,
            document_id=self.document_id,
            actors=self._extract_actors(obligations + rights),
            obligations=obligations,
            rights=rights,
            conditions=conditions,
            risks=risks,
            extraction_time_ms=elapsed,
            model_used=self.model_used,
            confidence_overall=confidence,
        )

    def _extract_obligations(
        self,
        text: str,
        chunk_id: str,
        section: str,
        section_name: str,
        page_number: int,
    ) -> list[Obligation]:
        """Extract obligations from text.

        Args:
            text: Text to search
            chunk_id: Chunk ID for evidence
            section: Section number
            section_name: Section name
            page_number: Page number

        Returns:
            List of extracted obligations
        """
        obligations = []

        for pattern in ObligationPatterns.all_patterns():
            matches = re.finditer(
                pattern.pattern,
                text,
                pattern.flags,
            )

            for match in matches:
                try:
                    actor_name = normalize_actor_name(match.group(pattern.groups["actor"]))
                    action = match.group(pattern.groups["action"]).strip()

                    # Skip empty/junk actions, but keep short real verbs like "pay"
                    if len(action) < 3:
                        continue

                    # Extract deadline if present
                    deadline = self._extract_deadline_from_text(action)

                    # Extract conditions
                    obligation_conditions = self._extract_conditions_for_obligation(text, action)

                    # Extract penalties
                    penalties = self._extract_penalties_from_text(action)

                    # Get source evidence
                    start_line = find_line_number(text, match.start())
                    quote = extract_text_around_match(text, match, context_chars=100)

                    evidence = Evidence(
                        document_id=self.document_id,
                        section=section,
                        section_name=section_name,
                        page_number=page_number,
                        line_numbers=f"{start_line}",
                        quote=quote.strip(),
                        confidence=0.85,
                    )

                    obligation = Obligation(
                        obligation_id=f"{chunk_id}-ob-{len(obligations)}",
                        actor=Actor(name=actor_name, role="Unknown"),
                        action=action,
                        severity=pattern.severity,
                        deadline=deadline,
                        conditions=obligation_conditions,
                        penalties=penalties,
                        evidence=evidence,
                        confidence=0.80,
                    )

                    obligations.append(obligation)

                except (IndexError, AttributeError):
                    # Failed to extract from this match, skip
                    continue

        return obligations

    def _extract_rights(
        self,
        text: str,
        chunk_id: str,
        section: str,
        section_name: str,
        page_number: int,
    ) -> list[Right]:
        """Extract rights from text.

        Args:
            text: Text to search
            chunk_id: Chunk ID for evidence
            section: Section number
            section_name: Section name
            page_number: Page number

        Returns:
            List of extracted rights
        """
        rights = []

        for pattern in RightPatterns.all_patterns():
            matches = re.finditer(
                pattern.pattern,
                text,
                pattern.flags,
            )

            for match in matches:
                try:
                    actor_name = normalize_actor_name(match.group(pattern.groups["actor"]))
                    action = match.group(pattern.groups["action"]).strip()

                    # Skip empty/junk actions, but keep short real verbs like "pay"
                    if len(action) < 3:
                        continue

                    # Extract conditions
                    right_conditions = self._extract_conditions_for_obligation(text, action)

                    # Extract limitations
                    limitations = self._extract_limitations_from_text(text, match.start(), action)

                    # Get source evidence
                    start_line = find_line_number(text, match.start())
                    quote = extract_text_around_match(text, match, context_chars=100)

                    evidence = Evidence(
                        document_id=self.document_id,
                        section=section,
                        section_name=section_name,
                        page_number=page_number,
                        line_numbers=f"{start_line}",
                        quote=quote.strip(),
                        confidence=0.85,
                    )

                    right = Right(
                        right_id=f"{chunk_id}-rt-{len(rights)}",
                        actor=Actor(name=actor_name, role="Unknown"),
                        action=action,
                        conditions=right_conditions,
                        limitations=limitations,
                        evidence=evidence,
                        confidence=0.80,
                    )

                    rights.append(right)

                except (IndexError, AttributeError):
                    continue

        return rights

    def _extract_conditions(self, text: str, chunk_id: str) -> list[Condition]:
        """Extract standalone conditions from text.

        Args:
            text: Text to search
            chunk_id: Chunk ID

        Returns:
            List of extracted conditions
        """
        conditions = []

        for pattern in ConditionPatterns.all_patterns():
            matches = re.finditer(
                pattern.pattern,
                text,
                pattern.flags,
            )

            for match in matches:
                try:
                    condition_text = match.group(pattern.groups.get("condition", 1)).strip()

                    # Determine condition type
                    if "unless" in pattern.name or "exception" in pattern.name:
                        cond_type = ConditionType.LIMITATION.value
                    elif "upon" in pattern.name or "event" in pattern.name:
                        cond_type = ConditionType.TRIGGER.value
                    elif "if" in pattern.name:
                        cond_type = ConditionType.TRIGGER.value
                    else:
                        cond_type = ConditionType.CONCURRENT.value

                    condition = Condition(
                        condition_type=cond_type,
                        description=condition_text,
                        confidence=0.75,
                    )

                    conditions.append(condition)

                except (IndexError, AttributeError):
                    continue

        # Remove duplicates
        seen = set()
        unique = []
        for cond in conditions:
            key = (cond.description.lower(), cond.condition_type)
            if key not in seen:
                seen.add(key)
                unique.append(cond)

        return unique

    def _extract_conditions_for_obligation(
        self,
        text: str,
        obligation_text: str,
    ) -> list[Condition]:
        """Extract conditions specific to an obligation.

        Args:
            text: Full text
            obligation_text: Text of obligation

        Returns:
            Conditions for this obligation
        """
        conditions = []

        # Look for conditions in the obligation text
        if "unless" in obligation_text.lower():
            match = re.search(r"unless\s+(.+?)(?:\.|$)", obligation_text, re.IGNORECASE)
            if match:
                conditions.append(
                    Condition(
                        condition_type=ConditionType.LIMITATION.value,
                        description=match.group(1).strip(),
                        confidence=0.85,
                    )
                )

        if "if" in obligation_text.lower():
            match = re.search(r"if\s+(.+?)(?:,|\.|\s+then|$)", obligation_text, re.IGNORECASE)
            if match:
                conditions.append(
                    Condition(
                        condition_type=ConditionType.TRIGGER.value,
                        description=match.group(1).strip(),
                        confidence=0.85,
                    )
                )

        if "provided that" in obligation_text.lower():
            match = re.search(r"provided\s+(?:that)?\s+(.+?)(?:\.|$)", obligation_text, re.IGNORECASE)
            if match:
                conditions.append(
                    Condition(
                        condition_type=ConditionType.CONCURRENT.value,
                        description=match.group(1).strip(),
                        confidence=0.85,
                    )
                )

        return conditions

    def _extract_deadline_from_text(self, text: str) -> Optional[Deadline]:
        """Extract deadline from text.

        Args:
            text: Text to search

        Returns:
            Deadline or None
        """
        # Check for relative deadline (within X days)
        match = re.search(
            r"within\s+(\d+)\s+(business\s+)?days?(?:\s+of)?",
            text,
            re.IGNORECASE,
        )
        if match:
            days = match.group(1)
            business = "business" in (match.group(2) or "")
            return Deadline(
                deadline_type=DeadlineType.RELATIVE.value,
                duration=f"{days} {'business ' if business else ''}days",
                confidence=0.90,
            )

        # Check for absolute deadline (by date)
        match = re.search(
            r"by\s+(\w+\s+\d{1,2},?\s+\d{4})",
            text,
            re.IGNORECASE,
        )
        if match:
            return Deadline(
                deadline_type=DeadlineType.ABSOLUTE.value,
                date=match.group(1),
                confidence=0.90,
            )

        return None

    def _extract_penalties_from_text(self, text: str) -> Optional[str]:
        """Extract penalties/consequences from text.

        Args:
            text: Text to search

        Returns:
            Penalty description or None
        """
        # Check for late fees
        match = re.search(
            r"(?:late\s+)?(?:fee|penalty|interest)\s+(?:of|at|is)?\s+([0-9.]+)%\s*(?:per\s+)?(\w+)?",
            text,
            re.IGNORECASE,
        )
        if match:
            rate = match.group(1)
            period = match.group(2) or "month"
            return f"{rate}% per {period}"

        return None

    def _extract_limitations_from_text(
        self,
        text: str,
        position: int,
        action_text: str,
    ) -> Optional[str]:
        """Extract limitations on a right.

        Args:
            text: Full text
            position: Position of right in text
            action_text: Action text

        Returns:
            Limitation text or None
        """
        # Look for "only if" or "except" after the right
        match = re.search(
            r"(?:only\s+)?(?:if|except)\s+(.+?)(?:\.|,|$|\n)",
            action_text,
            re.IGNORECASE,
        )
        if match:
            return match.group(1).strip()

        return None

    def _extract_actors(
        self,
        obligations_and_rights: list,
    ) -> list[Actor]:
        """Extract and deduplicate actors.

        Args:
            obligations_and_rights: List of obligations and rights

        Returns:
            Deduplicated list of actors
        """
        actors = {}
        for item in obligations_and_rights:
            actor = item.actor
            if actor.name not in actors:
                actors[actor.name] = actor
        return list(actors.values())

    def _classify_risks(
        self,
        obligations_and_rights: list,
        chunk_id: str,
    ) -> list[Risk]:
        """Classify risks from obligations and rights.

        Args:
            obligations_and_rights: List of obligations and rights
            chunk_id: Chunk ID

        Returns:
            List of classified risks
        """
        risks = []

        for i, item in enumerate(obligations_and_rights):
            risk_level = "MEDIUM"  # Default
            risk_cats = []
            probability = "POSSIBLE"

            # Determine risk level
            text = item.action.lower()

            if any(word in text for word in ["unlimited", "indemnify", "liable", "responsible"]):
                risk_level = "CRITICAL"
                risk_cats.append(RiskCategory.LEGAL.value)

            if any(word in text for word in ["pay", "payment", "fee", "cost", "liability"]):
                risk_level = "HIGH"
                risk_cats.append(RiskCategory.FINANCIAL.value)

            if any(word in text for word in ["terminate", "termination", "breach"]):
                risk_level = "CRITICAL"
                risk_cats.append(RiskCategory.TERMINATION.value)

            if any(word in text for word in ["confidential", "secret", "proprietary"]):
                risk_level = "HIGH"
                risk_cats.append(RiskCategory.COMPLIANCE.value)

            if any(word in text for word in ["deadline", "within", "days", "must"]):
                risk_level = "MEDIUM"
                risk_cats.append(RiskCategory.OPERATIONAL.value)

            # Default category if none assigned
            if not risk_cats:
                risk_cats = [RiskCategory.OPERATIONAL.value]

            risk = Risk(
                risk_id=f"{chunk_id}-risk-{i}",
                obligation_id=getattr(item, "obligation_id", None),
                risk_level=risk_level,
                risk_categories=risk_cats,
                probability=probability,
                description=f"Risk in: {item.action[:50]}",
                confidence=0.70,
            )

            risks.append(risk)

        return risks

    def batch_extract(
        self,
        texts: list[str],
        chunk_ids: list[str] = None,
    ) -> list[ExtractionResult]:
        """Extract from multiple texts.

        Args:
            texts: List of text chunks
            chunk_ids: Optional list of chunk IDs

        Returns:
            List of extraction results
        """
        results = []
        for i, text in enumerate(texts):
            chunk_id = chunk_ids[i] if chunk_ids else f"chunk-{i:03d}"
            result = self.extract(text, chunk_id=chunk_id)
            results.append(result)
        return results
