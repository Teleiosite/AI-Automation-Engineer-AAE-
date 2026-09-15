"""Workflow domain aggregate and WorkflowVersion entity."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4
from app.domain.enums import WorkflowStatus, WorkflowVersionStatus
from app.domain.errors import DomainValidationError, ImmutableArtifactError, InvariantViolationError


@dataclass
class WorkflowVersion:
    """Versioned workflow definition artifact."""
    workflow_id: UUID
    version_number: int
    specification_version_id: UUID
    definition: Dict[str, Any]
    id: UUID = field(default_factory=uuid4)
    status: WorkflowVersionStatus = WorkflowVersionStatus.DRAFT
    change_reason: str = "Initial version"
    created_by: str = "agent"
    provider_version_id: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if self.version_number < 1:
            raise DomainValidationError("Workflow version number must be >= 1")
        if not self.definition:
            raise DomainValidationError("Workflow definition cannot be empty")
        if self.created_at.tzinfo is None:
            raise DomainValidationError("Timestamps must be timezone-aware UTC")

    def update_definition(self, new_definition: Dict[str, Any], change_reason: str = "") -> None:
        """Modify definition; strictly forbidden once approved or deployed."""
        if self.status in (
            WorkflowVersionStatus.APPROVED,
            WorkflowVersionStatus.DEPLOYED,
            WorkflowVersionStatus.SUPERSEDED,
        ):
            raise ImmutableArtifactError(
                f"Workflow version {self.version_number} is in state '{self.status.value}' and cannot be modified"
            )
        if not new_definition:
            raise DomainValidationError("New definition cannot be empty")
        self.definition = new_definition
        if change_reason:
            self.change_reason = change_reason

    def validate(self) -> None:
        """Mark as structurally and semantically validated."""
        if self.status != WorkflowVersionStatus.DRAFT:
            raise InvariantViolationError(f"Cannot validate version in status '{self.status.value}'")
        self.status = WorkflowVersionStatus.VALIDATED

    def mark_tested(self) -> None:
        """Mark as tested."""
        if self.status != WorkflowVersionStatus.VALIDATED:
            raise InvariantViolationError("Version must be VALIDATED before marking as TESTED")
        self.status = WorkflowVersionStatus.TESTED

    def mark_approved(self) -> None:
        """Lock version upon formal approval."""
        if self.status != WorkflowVersionStatus.TESTED:
            raise InvariantViolationError("Version must be TESTED before marking as APPROVED")
        self.status = WorkflowVersionStatus.APPROVED

    def mark_deployed(self) -> None:
        """Mark as deployed."""
        if self.status != WorkflowVersionStatus.APPROVED:
            raise InvariantViolationError("Only APPROVED versions can be marked as DEPLOYED")
        self.status = WorkflowVersionStatus.DEPLOYED

    def supersede(self) -> None:
        """Supersede version when a new release is approved."""
        self.status = WorkflowVersionStatus.SUPERSEDED


@dataclass
class Workflow:
    """Logical workflow container."""
    project_id: UUID
    name: str
    id: UUID = field(default_factory=uuid4)
    environment: str = "development"
    status: WorkflowStatus = WorkflowStatus.DRAFT
    current_version_id: Optional[UUID] = None
    versions: List[WorkflowVersion] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise DomainValidationError("Workflow name cannot be empty")
        if self.created_at.tzinfo is None or self.updated_at.tzinfo is None:
            raise DomainValidationError("Timestamps must be timezone-aware UTC")

    def get_version(self, version_id: UUID) -> Optional[WorkflowVersion]:
        """Fetch version by UUID."""
        for v in self.versions:
            if v.id == version_id:
                return v
        return None

    def get_current_version(self) -> Optional[WorkflowVersion]:
        """Fetch current version."""
        if not self.current_version_id:
            return None
        return self.get_version(self.current_version_id)

    def add_version(
        self,
        specification_version_id: UUID,
        definition: Dict[str, Any],
        change_reason: str = "New revision",
        created_by: str = "agent",
    ) -> WorkflowVersion:
        """Create a new version for this workflow."""
        new_version_num = len(self.versions) + 1
        ver = WorkflowVersion(
            workflow_id=self.id,
            version_number=new_version_num,
            specification_version_id=specification_version_id,
            definition=definition,
            change_reason=change_reason,
            created_by=created_by,
        )
        self.versions.append(ver)
        self.current_version_id = ver.id
        self.updated_at = datetime.now(timezone.utc)
        return ver

    def activate(self) -> None:
        """Activate workflow in the target environment."""
        cur_ver = self.get_current_version()
        if not cur_ver or cur_ver.status != WorkflowVersionStatus.DEPLOYED:
            raise InvariantViolationError("Cannot activate workflow whose current version is not DEPLOYED")
        self.status = WorkflowStatus.ACTIVE
        self.updated_at = datetime.now(timezone.utc)

    def deactivate(self) -> None:
        """Deactivate workflow."""
        self.status = WorkflowStatus.INACTIVE
        self.updated_at = datetime.now(timezone.utc)

    def archive(self) -> None:
        """Archive workflow."""
        self.status = WorkflowStatus.ARCHIVED
        self.updated_at = datetime.now(timezone.utc)
