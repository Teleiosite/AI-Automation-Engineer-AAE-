"""Failure and Diagnostic domain models."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID, uuid4
from app.domain.enums import ConfidenceLevel, FailureCategory, FailureSeverity
from app.domain.errors import DomainValidationError


@dataclass(frozen=True)
class FailureRecord:
    """Provider-neutral representation of an execution failure."""
    execution_id: UUID
    category: FailureCategory
    severity: FailureSeverity
    failed_component: str
    message: str
    id: UUID = field(default_factory=uuid4)
    technical_details: Optional[Dict[str, Any]] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if not self.message or not self.message.strip():
            raise DomainValidationError("Failure message cannot be empty")
        if self.timestamp.tzinfo is None:
            raise DomainValidationError("Timestamps must be timezone-aware UTC")


@dataclass(frozen=True)
class DiagnosticFinding:
    """Root cause diagnostic finding produced by diagnosis engine."""
    failure_id: UUID
    likely_cause: str
    confidence: ConfidenceLevel
    recommended_action: str
    id: UUID = field(default_factory=uuid4)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if not self.likely_cause or not self.likely_cause.strip():
            raise DomainValidationError("Diagnostic likely cause cannot be empty")
        if self.timestamp.tzinfo is None:
            raise DomainValidationError("Timestamps must be timezone-aware UTC")
