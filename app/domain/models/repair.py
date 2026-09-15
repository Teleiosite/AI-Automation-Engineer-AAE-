"""Repair attempt domain model."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID, uuid4
from app.domain.enums import RiskLevel
from app.domain.errors import DomainValidationError


@dataclass
class RepairAttempt:
    """Controlled repair attempt for an identified automation failure."""
    workflow_id: UUID
    target_version_number: int
    failure_id: UUID
    diagnostic_id: UUID
    proposed_change: Dict[str, Any]
    id: UUID = field(default_factory=uuid4)
    risk: RiskLevel = RiskLevel.LOW
    status: str = "PROPOSED"
    initiated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        if self.target_version_number < 1:
            raise DomainValidationError("Target version number must be >= 1")
        if not self.proposed_change:
            raise DomainValidationError("Proposed repair change cannot be empty")
        if self.initiated_at.tzinfo is None:
            raise DomainValidationError("Timestamps must be timezone-aware UTC")

    def mark_applied(self) -> None:
        """Mark repair as applied for retesting."""
        self.status = "APPLIED"
        self.completed_at = datetime.now(timezone.utc)

    def mark_rejected(self) -> None:
        """Mark repair as rejected."""
        self.status = "REJECTED"
        self.completed_at = datetime.now(timezone.utc)
