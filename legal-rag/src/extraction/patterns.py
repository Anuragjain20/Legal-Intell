"""Pattern definitions for obligation and right extraction.

Contains regex patterns for identifying obligations, rights, conditions, and deadlines.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Pattern:
    """A regex pattern for extraction."""
    name: str
    pattern: str
    groups: dict[str, int]    # {"actor": 1, "action": 2, ...}
    severity: str = "MUST"
    flags: int = re.IGNORECASE


class ObligationPatterns:
    """Patterns for identifying obligations."""

    # Core obligation patterns
    OBLIGATION_SHALL = Pattern(
        name="obligation_shall",
        pattern=r"([A-Z][A-Za-z\s]+?)\s+shall\s+(.+?)(?=(?:unless|if|provided|;|or|\.|\n|$))",
        groups={"actor": 1, "action": 2},
        severity="MUST",
        flags=re.IGNORECASE | re.DOTALL
    )

    OBLIGATION_MUST = Pattern(
        name="obligation_must",
        pattern=r"([A-Z][A-Za-z\s]+?)\s+must\s+(.+?)(?=(?:unless|if|provided|;|or|\.|\n|$))",
        groups={"actor": 1, "action": 2},
        severity="MUST",
        flags=re.IGNORECASE | re.DOTALL
    )

    OBLIGATION_WILL = Pattern(
        name="obligation_will",
        pattern=r"([A-Z][A-Za-z\s]+?)\s+will\s+(.+?)(?=(?:unless|if|provided|;|or|\.|\n|$))",
        groups={"actor": 1, "action": 2},
        severity="MUST",
        flags=re.IGNORECASE | re.DOTALL
    )

    OBLIGATION_AGREES = Pattern(
        name="obligation_agrees",
        pattern=r"([A-Z][A-Za-z\s]+?)\s+agrees?\s+to\s+(.+?)(?=(?:unless|if|provided|;|or|\.|\n|$))",
        groups={"actor": 1, "action": 2},
        severity="MUST",
        flags=re.IGNORECASE | re.DOTALL
    )

    OBLIGATION_RESPONSIBLE = Pattern(
        name="obligation_responsible",
        pattern=r"([A-Z][A-Za-z\s]+?)\s+is\s+responsible\s+for\s+(.+?)(?=(?:unless|if|provided|;|or|\.|\n|$))",
        groups={"actor": 1, "action": 2},
        severity="MUST",
        flags=re.IGNORECASE | re.DOTALL
    )

    OBLIGATION_REQUIRED = Pattern(
        name="obligation_required",
        pattern=r"([A-Z][A-Za-z\s]+?)\s+(?:is\s+)?required\s+to\s+(.+?)(?=(?:unless|if|provided|;|or|\.|\n|$))",
        groups={"actor": 1, "action": 2},
        severity="MUST",
        flags=re.IGNORECASE | re.DOTALL
    )

    # Should/should not
    OBLIGATION_SHOULD = Pattern(
        name="obligation_should",
        pattern=r"([A-Z][A-Za-z\s]+?)\s+should\s+(.+?)(?=(?:unless|if|provided|;|or|\.|\n|$))",
        groups={"actor": 1, "action": 2},
        severity="SHOULD",
        flags=re.IGNORECASE | re.DOTALL
    )

    @classmethod
    def all_patterns(cls) -> list[Pattern]:
        """Return all obligation patterns."""
        return [
            cls.OBLIGATION_SHALL,
            cls.OBLIGATION_MUST,
            cls.OBLIGATION_WILL,
            cls.OBLIGATION_AGREES,
            cls.OBLIGATION_RESPONSIBLE,
            cls.OBLIGATION_REQUIRED,
            cls.OBLIGATION_SHOULD,
        ]


class RightPatterns:
    """Patterns for identifying rights."""

    RIGHT_MAY = Pattern(
        name="right_may",
        pattern=r"([A-Z][A-Za-z\s]+?)\s+may\s+(.+?)(?=(?:unless|if|provided|;|or|\.|\n|$))",
        groups={"actor": 1, "action": 2},
        severity="MAY",
        flags=re.IGNORECASE | re.DOTALL
    )

    RIGHT_CAN = Pattern(
        name="right_can",
        pattern=r"([A-Z][A-Za-z\s]+?)\s+can\s+(.+?)(?=(?:unless|if|provided|;|or|\.|\n|$))",
        groups={"actor": 1, "action": 2},
        severity="MAY",
        flags=re.IGNORECASE | re.DOTALL
    )

    RIGHT_HAS_RIGHT = Pattern(
        name="right_has_right_to",
        pattern=r"([A-Z][A-Za-z\s]+?)\s+has\s+the\s+right\s+to\s+(.+?)(?=(?:unless|if|provided|;|or|\.|\n|$))",
        groups={"actor": 1, "action": 2},
        severity="MAY",
        flags=re.IGNORECASE | re.DOTALL
    )

    RIGHT_ENTITLED = Pattern(
        name="right_entitled",
        pattern=r"([A-Z][A-Za-z\s]+?)\s+(?:is\s+)?entitled\s+to\s+(.+?)(?=(?:unless|if|provided|;|or|\.|\n|$))",
        groups={"actor": 1, "action": 2},
        severity="MAY",
        flags=re.IGNORECASE | re.DOTALL
    )

    RIGHT_PERMITTED = Pattern(
        name="right_permitted",
        pattern=r"([A-Z][A-Za-z\s]+?)\s+(?:is\s+)?permitted\s+to\s+(.+?)(?=(?:unless|if|provided|;|or|\.|\n|$))",
        groups={"actor": 1, "action": 2},
        severity="MAY",
        flags=re.IGNORECASE | re.DOTALL
    )

    @classmethod
    def all_patterns(cls) -> list[Pattern]:
        """Return all right patterns."""
        return [
            cls.RIGHT_MAY,
            cls.RIGHT_CAN,
            cls.RIGHT_HAS_RIGHT,
            cls.RIGHT_ENTITLED,
            cls.RIGHT_PERMITTED,
        ]


class ConditionPatterns:
    """Patterns for identifying conditions."""

    # Triggering conditions
    CONDITION_IF = Pattern(
        name="condition_if",
        pattern=r"(?:if|when)\s+(.+?)(?:,?\s+then|\s+the|\.|\n|$)",
        groups={"condition": 1},
        flags=re.IGNORECASE | re.DOTALL
    )

    CONDITION_UNLESS = Pattern(
        name="condition_unless",
        pattern=r"(?:unless|except\s+(?:if|that)|except\s+when)\s+(.+?)(?:\.|,|$|\n)",
        groups={"condition": 1},
        flags=re.IGNORECASE | re.DOTALL
    )

    CONDITION_PROVIDED = Pattern(
        name="condition_provided",
        pattern=r"provided\s+(?:that)?\s+(.+?)(?:\.|,|$|\n)",
        groups={"condition": 1},
        flags=re.IGNORECASE | re.DOTALL
    )

    CONDITION_UPON = Pattern(
        name="condition_upon",
        pattern=r"(?:upon|on)\s+(.+?)(?:,?\s+(?:the|[A-Z])|\.|\n|$)",
        groups={"condition": 1},
        flags=re.IGNORECASE | re.DOTALL
    )

    CONDITION_IN_EVENT = Pattern(
        name="condition_in_event",
        pattern=r"(?:in\s+(?:the\s+)?event\s+of|in\s+case\s+of)\s+(.+?)(?:,|\.|$|\n)",
        groups={"condition": 1},
        flags=re.IGNORECASE | re.DOTALL
    )

    CONDITION_CONTINGENT = Pattern(
        name="condition_contingent",
        pattern=r"(?:contingent\s+upon|subject\s+to|conditioned\s+(?:upon|on))\s+(.+?)(?:,|\.|$|\n)",
        groups={"condition": 1},
        flags=re.IGNORECASE | re.DOTALL
    )

    @classmethod
    def all_patterns(cls) -> list[Pattern]:
        """Return all condition patterns."""
        return [
            cls.CONDITION_IF,
            cls.CONDITION_UNLESS,
            cls.CONDITION_PROVIDED,
            cls.CONDITION_UPON,
            cls.CONDITION_IN_EVENT,
            cls.CONDITION_CONTINGENT,
        ]


class DeadlinePatterns:
    """Patterns for identifying deadlines."""

    # Absolute dates
    DEADLINE_BY_DATE = Pattern(
        name="deadline_by_date",
        pattern=r"(?:by|before|on|no\s+later\s+than)\s+(\d{1,2})\s+([A-Za-z]+)\s+,?\s*(\d{4})",
        groups={"day": 1, "month": 2, "year": 3},
        flags=re.IGNORECASE
    )

    # Relative durations
    DEADLINE_WITHIN = Pattern(
        name="deadline_within",
        pattern=r"(?:within|in)\s+(\d+)\s+(business\s+)?days?(?:\s+of)?",
        groups={"duration": 1, "business": 2},
        flags=re.IGNORECASE
    )

    DEADLINE_AFTER = Pattern(
        name="deadline_after",
        pattern=r"(?:after|following)\s+(\d+)\s+(business\s+)?days?(?:\s+of)?",
        groups={"duration": 1, "business": 2},
        flags=re.IGNORECASE
    )

    # Relative to events
    DEADLINE_OF_EVENT = Pattern(
        name="deadline_of_event",
        pattern=r"(?:within|within\s+\d+\s+days\s+of|upon)\s+([A-Za-z\s]+?)(?:\.|,|$|\n)",
        groups={"event": 1},
        flags=re.IGNORECASE | re.DOTALL
    )

    # Recurring
    DEADLINE_QUARTERLY = Pattern(
        name="deadline_quarterly",
        pattern=r"(?:quarterly|semi-annually?|annually?|monthly?|weekly?)",
        groups={},
        flags=re.IGNORECASE
    )

    @classmethod
    def all_patterns(cls) -> list[Pattern]:
        """Return all deadline patterns."""
        return [
            cls.DEADLINE_BY_DATE,
            cls.DEADLINE_WITHIN,
            cls.DEADLINE_AFTER,
            cls.DEADLINE_OF_EVENT,
            cls.DEADLINE_QUARTERLY,
        ]


class PenaltyPatterns:
    """Patterns for identifying penalties/consequences."""

    PENALTY_LATE_FEE = Pattern(
        name="penalty_late_fee",
        pattern=r"(?:late\s+)?(?:fee|charge|penalty|interest)\s+(?:of|at|is)?\s+([0-9.]+)%\s*(?:per\s+)?(\w+)?",
        groups={"rate": 1, "period": 2},
        flags=re.IGNORECASE
    )

    PENALTY_TERMINATION = Pattern(
        name="penalty_termination",
        pattern=r"(?:breach|failure|non-compliance)\s+(?:shall\s+)?(?:result\s+)?(?:in|allows?)\s+(?:immediate\s+)?termination",
        groups={},
        flags=re.IGNORECASE
    )

    PENALTY_LIABILITY = Pattern(
        name="penalty_liability",
        pattern=r"(?:liable|responsible)\s+(?:for\s+)?(.+?)(?:damages?|liability|losses?)",
        groups={"type": 1},
        flags=re.IGNORECASE
    )

    @classmethod
    def all_patterns(cls) -> list[Pattern]:
        """Return all penalty patterns."""
        return [
            cls.PENALTY_LATE_FEE,
            cls.PENALTY_TERMINATION,
            cls.PENALTY_LIABILITY,
        ]


def extract_text_around_match(text: str, match_obj, context_chars: int = 50) -> str:
    """Extract text around a match for context.

    Args:
        text: Full text
        match_obj: Regex match object
        context_chars: Characters before/after to include

    Returns:
        Text with context
    """
    start = max(0, match_obj.start() - context_chars)
    end = min(len(text), match_obj.end() + context_chars)
    return text[start:end]


def find_line_number(text: str, position: int) -> int:
    """Find line number for a position in text.

    Args:
        text: Full text
        position: Character position

    Returns:
        1-indexed line number
    """
    return text[:position].count('\n') + 1


def normalize_actor_name(name: str) -> str:
    """Normalize actor name for consistency.

    Args:
        name: Actor name from text

    Returns:
        Normalized name
    """
    # Remove articles
    name = re.sub(r'^\s*(the|a|an)\s+', '', name, flags=re.IGNORECASE)
    # Remove extra whitespace
    name = ' '.join(name.split())
    # Capitalize properly
    name = ' '.join(word.capitalize() for word in name.split())
    return name
