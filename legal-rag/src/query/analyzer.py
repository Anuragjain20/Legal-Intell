"""Query analysis and normalization."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass

from src.query.models import LegalTermSignal, NormalizedQuery, QueryIntent, QuerySignal


# Legal terms and their associated intents
LEGAL_TERMS = {
    # Obligations
    "shall": QueryIntent.OBLIGATION,
    "must": QueryIntent.OBLIGATION,
    "required": QueryIntent.OBLIGATION,
    "obligation": QueryIntent.OBLIGATION,
    "duty": QueryIntent.OBLIGATION,
    "liable": QueryIntent.OBLIGATION,
    "responsible": QueryIntent.OBLIGATION,
    "disclose": QueryIntent.OBLIGATION,
    # Rights
    "right": QueryIntent.RIGHT,
    "entitled": QueryIntent.RIGHT,
    "may": QueryIntent.RIGHT,
    "permission": QueryIntent.RIGHT,
    "authority": QueryIntent.RIGHT,
    "license": QueryIntent.RIGHT,
    # Conditions
    "if": QueryIntent.CONDITION,
    "condition": QueryIntent.CONDITION,
    "conditional": QueryIntent.CONDITION,
    "provided": QueryIntent.CONDITION,
    "subject to": QueryIntent.CONDITION,
    "upon": QueryIntent.CONDITION,
    # Procedures
    "procedure": QueryIntent.PROCEDURE,
    "process": QueryIntent.PROCEDURE,
    "steps": QueryIntent.PROCEDURE,
    "how": QueryIntent.PROCEDURE,
    "method": QueryIntent.PROCEDURE,
    "implement": QueryIntent.PROCEDURE,
    # Definitions
    "definition": QueryIntent.DEFINITION,
    "means": QueryIntent.DEFINITION,
    "mean": QueryIntent.DEFINITION,
    "defined": QueryIntent.DEFINITION,
    "definition of": QueryIntent.DEFINITION,
    "what is": QueryIntent.DEFINITION,
    # Scope
    "scope": QueryIntent.SCOPE,
    "apply": QueryIntent.SCOPE,
    "applicable": QueryIntent.SCOPE,
    "covers": QueryIntent.SCOPE,
    "extent": QueryIntent.SCOPE,
    # Temporal
    "when": QueryIntent.TEMPORAL,
    "time": QueryIntent.TEMPORAL,
    "period": QueryIntent.TEMPORAL,
    "duration": QueryIntent.TEMPORAL,
    "effective": QueryIntent.TEMPORAL,
    "date": QueryIntent.TEMPORAL,
    "terminate": QueryIntent.TEMPORAL,
    "expiration": QueryIntent.TEMPORAL,
}

NEGATION_WORDS = {"not", "no", "never", "cannot", "can't", "won't", "shouldn't", "doesn't", "don't"}

TEMPORAL_WORDS = {"when", "after", "before", "during", "until", "since", "upon", "date", "time", "period", "terminate"}

SECTION_PATTERN = re.compile(r"\b(\d+(?:\.\d+)*(?:\([a-z]\))?)\b", re.IGNORECASE)
QUOTED_PATTERN = re.compile(r'"([^"]+)"')


@dataclass
class QueryAnalyzer:
    """Deterministic query analysis and normalization."""

    def analyze(self, query: str) -> NormalizedQuery:
        """Analyze raw query and return normalized representation."""
        start_time = time.time()

        if not query or not query.strip():
            raise ValueError("Query must not be blank.")

        original = query
        normalized = self._normalize_whitespace(query)

        intent = self._detect_intent(normalized)
        legal_terms = self._extract_legal_terms(normalized)
        retrieval_signals = self._extract_retrieval_signals(normalized, legal_terms)
        exact_matches = self._extract_quoted_terms(query)
        has_negation = self._detect_negation(normalized)
        has_temporal = self._detect_temporal_constraint(normalized)

        processing_time_ms = (time.time() - start_time) * 1000

        return NormalizedQuery(
            original=original,
            normalized=normalized,
            intent=intent,
            legal_terms=legal_terms,
            retrieval_signals=retrieval_signals,
            exact_matches=exact_matches,
            has_negation=has_negation,
            has_temporal_constraint=has_temporal,
            processing_time_ms=processing_time_ms,
        )

    def _normalize_whitespace(self, query: str) -> str:
        """Normalize whitespace and case."""
        # Collapse multiple spaces
        normalized = re.sub(r"\s+", " ", query).strip()
        return normalized

    def _detect_intent(self, query: str) -> QueryIntent:
        """Detect the primary intent of the query."""
        query_lower = query.lower()
        # Count matches per intent, and track each intent's earliest match
        # position as a tiebreak - the first legal term a question raises is
        # usually its real subject, ahead of an incidental later mention.
        intent_counts: dict[QueryIntent, int] = {}
        intent_first_pos: dict[QueryIntent, int] = {}

        for term, intent in LEGAL_TERMS.items():
            position = query_lower.find(term)
            if position != -1:
                intent_counts[intent] = intent_counts.get(intent, 0) + 1
                intent_first_pos[intent] = min(intent_first_pos.get(intent, position), position)

        # Return the intent with the most matches, breaking ties by whichever
        # matched earliest in the query, or default to general inquiry.
        if intent_counts:
            return max(intent_counts, key=lambda i: (intent_counts[i], -intent_first_pos[i]))

        # Heuristic fallbacks
        if "how" in query_lower or "what" in query_lower or "why" in query_lower:
            return QueryIntent.GENERAL_INQUIRY
        if "which" in query_lower or "where" in query_lower:
            return QueryIntent.SCOPE
        if "when" in query_lower:
            return QueryIntent.TEMPORAL

        return QueryIntent.GENERAL_INQUIRY

    def _extract_legal_terms(self, query: str) -> list[LegalTermSignal]:
        """Extract legal terms and phrases from query."""
        query_lower = query.lower()
        signals: list[LegalTermSignal] = []
        seen = set()

        for term in LEGAL_TERMS.keys():
            if term in query_lower and term not in seen:
                # Match on a word start so plurals/suffixes count (e.g. "obligation"
                # inside "obligations"), while still rejecting mid-word substrings.
                pattern = rf"\b{re.escape(term)}"
                if re.search(pattern, query_lower):
                    # Extract potential section references near the term
                    section = None
                    for section_match in SECTION_PATTERN.finditer(query):
                        section = section_match.group(1)
                        break

                    signals.append(
                        LegalTermSignal(
                            term=term,
                            confidence=0.9,
                            is_quoted=False,
                            potential_section=section,
                        )
                    )
                    seen.add(term)

        return signals

    def _extract_quoted_terms(self, query: str) -> list[str]:
        """Extract exact quoted terms from query."""
        matches = QUOTED_PATTERN.findall(query)
        return matches

    def _extract_retrieval_signals(
        self, query: str, legal_terms: list[LegalTermSignal]
    ) -> list[QuerySignal]:
        """Extract signals for retrieval optimization."""
        signals: list[QuerySignal] = []

        # Add legal terms as high-confidence signals
        for term_signal in legal_terms:
            signals.append(
                QuerySignal(
                    signal=term_signal.term,
                    weight=0.9,
                    category="legal_term",
                )
            )

        # Extract key noun phrases (nouns followed by nouns)
        words = query.lower().split()
        for i in range(len(words) - 1):
            word = words[i]
            # Look for important words that might be key terms
            if len(word) > 4 and not word in {"that", "this", "then", "when", "what", "which"}:
                if words[i + 1] not in LEGAL_TERMS and len(words[i + 1]) > 3:
                    signals.append(
                        QuerySignal(
                            signal=f"{word} {words[i + 1]}",
                            weight=0.6,
                            category="noun_phrase",
                        )
                    )
                    break  # Only take the first prominent phrase

        return signals

    def _detect_negation(self, query: str) -> bool:
        """Detect if query contains negation."""
        query_lower = query.lower()
        return any(word in query_lower for word in NEGATION_WORDS)

    def _detect_temporal_constraint(self, query: str) -> bool:
        """Detect if query has temporal constraints."""
        query_lower = query.lower()
        return any(word in query_lower for word in TEMPORAL_WORDS)
