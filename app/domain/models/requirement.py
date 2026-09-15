"""Requirement domain entity and RequirementItem value object."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID, uuid4
from app.domain.enums import ConfidenceLevel, RequirementType, RiskLevel
from app.domain.errors import DomainValidationError, InvariantViolationError


@dataclass(frozen=True)
class RequirementItem:
    """Individual extracted requirement component with confidence and risk."""
    type: RequirementType
    description: str
    confidence: ConfidenceLevel
    risk: RiskLevel = RiskLevel.LOW
    id: UUID = field(default_factory=uuid4)
    notes: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.description or not self.description.strip():
            raise DomainValidationError("RequirementItem description cannot be empty")


@dataclass
class Requirement:
    """Requirement aggregate preserving immutable user request and parsed items."""
    project_id: UUID
    original_request: str
    id: UUID = field(default_factory=uuid4)
    created_by: str = "user"
    version: int = 1
    items: List[RequirementItem] = field(default_factory=list)
    assumptions: List[str] = field(default_factory=list)
    ambiguities: List[str] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if not self.original_request or not self.original_request.strip():
            raise DomainValidationError("Original user request cannot be empty")
        if self.version < 1:
            raise DomainValidationError("Requirement version must be >= 1")
        if self.created_at.tzinfo is None:
            raise DomainValidationError("Timestamps must be timezone-aware UTC")

    def add_item(self, item: RequirementItem) -> None:
        """Add an extracted requirement component."""
        self.items.append(item)

    def add_conflict(self, conflict_description: str) -> None:
        """Record a conflict between requirements."""
        self.conflicts.append(conflict_description)

    def has_unresolved_conflicts(self) -> bool:
        """Check if requirement has conflicting items or notes."""
        if self.conflicts:
            return True
        return any(item.confidence == ConfidenceLevel.CONFLICTING for item in self.items)

    def has_ambiguities(self) -> bool:
        """Check if ambiguities remain."""
        if self.ambiguities:
            return True
        return any(item.confidence == ConfidenceLevel.UNKNOWN for item in self.items)

    def add_assumption(self, assumption: str) -> None:
        """Record an explicit or inferred assumption."""
        self.assumptions.append(assumption)

    def add_ambiguity(self, ambiguity_description: str) -> None:
        """Record an identified ambiguity or gap."""
        self.ambiguities.append(ambiguity_description)

    def overall_risk(self) -> RiskLevel:
        """Calculate highest risk across all extracted requirement items."""
        risk_hierarchy = {
            RiskLevel.LOW: 1,
            RiskLevel.MEDIUM: 2,
            RiskLevel.HIGH: 3,
            RiskLevel.CRITICAL: 4,
        }
        if not self.items:
            return RiskLevel.LOW
        highest_score = max(risk_hierarchy.get(item.risk, 1) for item in self.items)
        for level, score in risk_hierarchy.items():
            if score == highest_score:
                return level
        return RiskLevel.LOW

    def assert_ready_for_specification(self) -> None:
        """Enforces that conflicting or ambiguous requirements cannot proceed without clarification."""
        if self.has_unresolved_conflicts():
            raise InvariantViolationError("Cannot specify requirement with unresolved conflicts")
        if self.has_ambiguities():
            raise InvariantViolationError("Cannot specify requirement with unresolved ambiguities")
