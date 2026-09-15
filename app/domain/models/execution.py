"""Execution aggregate and ExecutionResult value object."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID, uuid4
from app.domain.enums import ExecutionStatus, SemanticStatus, TechnicalStatus, TriggerType
from app.domain.errors import DomainValidationError, InvariantViolationError


@dataclass(frozen=True)
class ExecutionResult:
    """
    Execution outcome explicitly distinguishing technical execution from semantic business success.
    An automation can technically succeed (HTTP 200) while failing semantic business criteria.
    """
    technical_status: TechnicalStatus
    semantic_status: SemanticStatus
    duration_ms: float = 0.0
    output_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        if self.duration_ms < 0:
            raise DomainValidationError("Execution duration cannot be negative")


@dataclass
class Execution:
    """Execution run instance."""
    workflow_id: UUID
    workflow_version_id: UUID
    id: UUID = field(default_factory=uuid4)
    status: ExecutionStatus = ExecutionStatus.QUEUED
    trigger_type: TriggerType = TriggerType.MANUAL
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: Optional[datetime] = None
    result: Optional[ExecutionResult] = None
    correlation_id: Optional[str] = None

    def __post_init__(self) -> None:
        if self.started_at.tzinfo is None:
            raise DomainValidationError("Timestamps must be timezone-aware UTC")
        if self.finished_at is not None and self.finished_at.tzinfo is None:
            raise DomainValidationError("Timestamps must be timezone-aware UTC")

    def start(self) -> None:
        """Mark execution as actively running."""
        if self.status != ExecutionStatus.QUEUED:
            raise InvariantViolationError(f"Cannot start execution in state '{self.status.value}'")
        self.status = ExecutionStatus.RUNNING

    def complete(self, result: ExecutionResult, finished_at: Optional[datetime] = None) -> None:
        """Complete the execution and bind technical & semantic results."""
        if self.status not in (ExecutionStatus.RUNNING, ExecutionStatus.QUEUED):
            raise InvariantViolationError(f"Cannot complete execution in state '{self.status.value}'")

        end_time = finished_at or datetime.now(timezone.utc)
        if end_time.tzinfo is None:
            raise DomainValidationError("Timestamps must be timezone-aware UTC")
        if end_time < self.started_at:
            raise InvariantViolationError("Execution finished_at cannot precede started_at")

        self.finished_at = end_time
        self.result = result

        if result.technical_status == TechnicalStatus.SUCCESS:
            self.status = ExecutionStatus.SUCCESS
        elif result.technical_status == TechnicalStatus.ERROR:
            self.status = ExecutionStatus.FAILURE
        else:
            self.status = ExecutionStatus.FAILURE
