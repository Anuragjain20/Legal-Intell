"""Data models for legal obligation and risk extraction.

Defines structures for:
- Obligations and Rights
- Conditions and Deadlines
- Risks and their classification
- Evidence/source references
- Extraction results
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ObligationType(Enum):
    """Types of legal obligations."""
    OBLIGATION = "obligation"
    RIGHT = "right"
    CONDITION = "condition"
    RISK = "risk"


class SeverityLevel(Enum):
    """Obligation severity."""
    MUST = "must"        # Required
    SHOULD = "should"    # Strongly recommended
    MAY = "may"          # Optional/permissive


class RiskLevel(Enum):
    """Risk severity classification."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RiskCategory(Enum):
    """Risk type categories."""
    FINANCIAL = "financial"
    OPERATIONAL = "operational"
    LEGAL = "legal"
    REPUTATIONAL = "reputational"
    COMPLIANCE = "compliance"
    TERMINATION = "termination"


class ConditionType(Enum):
    """Types of conditions."""
    TRIGGER = "trigger"        # Activates obligation
    LIMITATION = "limitation"  # Restricts obligation
    CONCURRENT = "concurrent"  # Must happen together
    EXCEPTION = "exception"    # Exception to obligation


class DeadlineType(Enum):
    """Deadline classification."""
    ABSOLUTE = "absolute"      # Specific date
    RELATIVE = "relative"      # Duration (e.g., 30 days)
    TRIGGERED = "triggered"    # Relative to event
    RECURRING = "recurring"    # Periodic


class Favorability(Enum):
    """Whether change is favorable or not."""
    FAVORABLE = "favorable"
    NEUTRAL = "neutral"
    UNFAVORABLE = "unfavorable"


class ChangeType(Enum):
    """Types of document changes."""
    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"
    MOVED = "moved"
    UNCHANGED = "unchanged"


@dataclass(frozen=True)
class Evidence:
    """Source reference for extracted information."""

    document_id: str
    section: str              # "4.2"
    section_name: str         # "Payment Terms"
    page_number: int
    line_numbers: str         # "12-15"
    quote: str                # Exact text from document
    confidence: float         # 0.0-1.0


@dataclass(frozen=True)
class Actor:
    """Party/actor in the agreement."""

    name: str                 # "Buyer", "Seller"
    aliases: list[str] = None # ["Purchaser", "Licensee"]
    entity_type: str = "PARTY"  # "INDIVIDUAL", "CORPORATION", "PARTY"
    role: str = None          # "Buyer", "Seller", "Service Provider"

    def __post_init__(self):
        if self.aliases is None:
            object.__setattr__(self, 'aliases', [])


@dataclass(frozen=True)
class Deadline:
    """Temporal constraint on obligation."""

    deadline_type: str        # "ABSOLUTE", "RELATIVE", "TRIGGERED", "RECURRING"
    date: Optional[str] = None       # "2025-06-01" for ABSOLUTE
    duration: Optional[str] = None   # "30 days" for RELATIVE
    trigger_event: Optional[str] = None  # "Upon invoice receipt" for TRIGGERED
    frequency: Optional[str] = None  # "Quarterly" for RECURRING
    confidence: float = 0.9


@dataclass(frozen=True)
class Condition:
    """Triggering or limiting condition."""

    condition_type: str       # "TRIGGER", "LIMITATION", "CONCURRENT", "EXCEPTION"
    description: str          # "If weather prevents delivery"
    related_obligation_id: Optional[str] = None
    confidence: float = 0.9


@dataclass(frozen=True)
class Obligation:
    """Extracted obligation from text."""

    obligation_id: str
    actor: Actor
    action: str               # "Deliver goods", "Pay invoice"
    severity: str = "MUST"    # "MUST", "SHOULD", "MAY"
    deadline: Optional[Deadline] = None
    conditions: list[Condition] = None
    penalties: Optional[str] = None  # "5% late fee per month"
    evidence: Optional[Evidence] = None
    confidence: float = 0.9

    def __post_init__(self):
        if self.conditions is None:
            object.__setattr__(self, 'conditions', [])


@dataclass(frozen=True)
class Right:
    """Extracted right/permission from text."""

    right_id: str
    actor: Actor
    action: str               # "Terminate contract", "Audit records"
    conditions: list[Condition] = None
    limitations: Optional[str] = None  # "Only if written notice provided"
    evidence: Optional[Evidence] = None
    confidence: float = 0.9

    def __post_init__(self):
        if self.conditions is None:
            object.__setattr__(self, 'conditions', [])


@dataclass(frozen=True)
class Risk:
    """Risk classification for obligation/right."""

    risk_id: str
    obligation_id: Optional[str]  # Which obligation creates this risk
    risk_level: str           # "CRITICAL", "HIGH", "MEDIUM", "LOW"
    risk_categories: list[str]  # ["FINANCIAL", "LEGAL", "TERMINATION"]
    probability: str = "POSSIBLE"  # "LIKELY", "POSSIBLE", "UNLIKELY"
    description: str = ""
    mitigation: Optional[str] = None  # "Add liability cap to Section 8"
    priority_score: float = 0.5  # 0.0-1.0 (higher = more urgent)
    confidence: float = 0.9

    def __post_init__(self):
        if self.risk_categories is None:
            object.__setattr__(self, 'risk_categories', [])


@dataclass(frozen=True)
class ExtractionResult:
    """Complete extraction from a chunk."""

    chunk_id: str
    document_id: str

    actors: list[Actor]
    obligations: list[Obligation]
    rights: list[Right]
    conditions: list[Condition]

    risks: list[Risk]

    extraction_time_ms: float
    model_used: str
    confidence_overall: float

    def __post_init__(self):
        # Ensure all lists are initialized
        if not hasattr(self, 'actors'):
            object.__setattr__(self, 'actors', [])
        if not hasattr(self, 'obligations'):
            object.__setattr__(self, 'obligations', [])
        if not hasattr(self, 'rights'):
            object.__setattr__(self, 'rights', [])
        if not hasattr(self, 'conditions'):
            object.__setattr__(self, 'conditions', [])
        if not hasattr(self, 'risks'):
            object.__setattr__(self, 'risks', [])

    @property
    def risk_summary(self) -> dict:
        """Count risks by level."""
        summary = {level.name: 0 for level in RiskLevel}
        for risk in self.risks:
            summary[risk.risk_level] += 1
        return summary


# Document Comparison Models

@dataclass(frozen=True)
class ClauseLocation:
    """Where a clause exists in document."""

    document_id: str
    section: str              # "4.2"
    section_name: str         # "Payment Terms"
    page_number: int
    line_numbers: str         # "12-15"
    subsection_path: list[str] = None  # ["4", "2", "a"]

    def __post_init__(self):
        if self.subsection_path is None:
            object.__setattr__(self, 'subsection_path', [])


@dataclass(frozen=True)
class TextChange:
    """Specific text change within a clause."""

    change_type: str          # "NUMERIC", "CONDITIONAL", "SCOPE", "DEFINITION"
    location: str             # "deadline", "penalty_rate", "scope"
    old_value: Optional[str]
    new_value: Optional[str]
    magnitude: str = "MODERATE"  # "MAJOR", "MODERATE", "MINOR"
    impact: str = "NEUTRAL"   # "FAVORABLE", "NEUTRAL", "UNFAVORABLE"


@dataclass(frozen=True)
class Clause:
    """Extracted clause from document."""

    clause_id: str
    title: str                # "Payment Terms"
    text: str
    location: ClauseLocation
    obligations: list[str] = None  # IDs of obligations
    embedding: Optional[list[float]] = None

    def __post_init__(self):
        if self.obligations is None:
            object.__setattr__(self, 'obligations', [])


@dataclass(frozen=True)
class ClauseComparison:
    """Comparison of two versions of a clause."""

    clause_id: str
    change_type: str          # "ADDED", "REMOVED", "MODIFIED", "MOVED", "UNCHANGED"

    # For ADDED/REMOVED
    clause_v1: Optional[Clause] = None  # None if ADDED
    clause_v2: Optional[Clause] = None  # None if REMOVED

    # For MODIFIED
    text_changes: list[TextChange] = None
    similarity_score: float = 1.0  # 0.0-1.0

    # Impact assessment
    favorability: str = "NEUTRAL"     # "FAVORABLE", "NEUTRAL", "UNFAVORABLE"
    magnitude: str = "MINOR"          # "MAJOR", "MODERATE", "MINOR"
    risk_level: str = "LOW"           # "CRITICAL", "HIGH", "MEDIUM", "LOW"

    # For MOVED
    old_location: Optional[ClauseLocation] = None
    new_location: Optional[ClauseLocation] = None

    # Overall assessment
    impact_score: float = 0.0  # 0.0-1.0 (higher = more impactful)
    summary: str = ""
    recommendation: str = ""

    def __post_init__(self):
        if self.text_changes is None:
            object.__setattr__(self, 'text_changes', [])


@dataclass(frozen=True)
class DocumentComparison:
    """Complete comparison between two documents."""

    document_v1_id: str
    document_v2_id: str

    comparisons: list[ClauseComparison]

    # Aggregates
    added_count: int = 0
    removed_count: int = 0
    modified_count: int = 0
    moved_count: int = 0
    unchanged_count: int = 0

    # Summary statistics
    favorable_changes: int = 0
    unfavorable_changes: int = 0
    critical_risks_introduced: int = 0

    # Recommendations
    critical_items: list[ClauseComparison] = None
    favorable_items: list[ClauseComparison] = None

    comparison_time_ms: float = 0.0
    confidence_score: float = 0.9

    def __post_init__(self):
        if self.critical_items is None:
            object.__setattr__(self, 'critical_items', [])
        if self.favorable_items is None:
            object.__setattr__(self, 'favorable_items', [])

    @property
    def total_changes(self) -> int:
        """Total number of changes."""
        return (self.added_count + self.removed_count +
                self.modified_count + self.moved_count)

    @property
    def change_summary(self) -> dict:
        """Summary of changes by type."""
        return {
            "added": self.added_count,
            "removed": self.removed_count,
            "modified": self.modified_count,
            "moved": self.moved_count,
            "unchanged": self.unchanged_count,
            "total_changes": self.total_changes,
        }
