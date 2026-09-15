"""Deployment domain entity."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4
from app.domain.enums import DeploymentStatus
from app.domain.errors import DomainValidationError, InvariantViolationError


@dataclass
class Deployment:
    """Deployment record representing an automation release into a target environment."""
    workflow_id: UUID
    workflow_version_id: UUID
    workflow_version_number: int
    target_environment: str
    deployed_by: str
    id: UUID = field(default_factory=uuid4)
    approval_id: Optional[UUID] = None
    status: DeploymentStatus = DeploymentStatus.PENDING
    deployed_at: Optional[datetime] = None
    error_message: Optional[str] = None

    def __post_init__(self) -> None:
        if self.workflow_version_number < 1:
            raise DomainValidationError("Workflow version number must be >= 1")
        if not self.target_environment or not self.target_environment.strip():
            raise DomainValidationError("Target environment cannot be empty")
        if not self.deployed_by or not self.deployed_by.strip():
            raise DomainValidationError("Deployed by actor cannot be empty")
        if self.deployed_at is not None and self.deployed_at.tzinfo is None:
            raise DomainValidationError("Timestamps must be timezone-aware UTC")

    def mark_in_progress(self) -> None:
        """Begin deployment execution."""
        if self.status != DeploymentStatus.PENDING:
            raise InvariantViolationError(f"Cannot start deployment in status '{self.status.value}'")
        self.status = DeploymentStatus.IN_PROGRESS

    def mark_deployed(self, deployed_at: Optional[datetime] = None) -> None:
        """Record successful deployment."""
        if self.status != DeploymentStatus.IN_PROGRESS:
            raise InvariantViolationError(f"Cannot mark deployment as DEPLOYED from '{self.status.value}'")
        self.status = DeploymentStatus.DEPLOYED
        self.deployed_at = deployed_at or datetime.now(timezone.utc)

    def mark_failed(self, error: str) -> None:
        """Record deployment failure."""
        self.status = DeploymentStatus.FAILED
        self.error_message = error

    def mark_rolled_back(self) -> None:
        """Record rollback."""
        if self.status != DeploymentStatus.DEPLOYED:
            raise InvariantViolationError("Can only rollback a DEPLOYED release")
        self.status = DeploymentStatus.ROLLED_BACK
