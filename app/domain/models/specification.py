"""Specification domain entity and SpecificationVersion."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4
from app.domain.enums import SpecificationStatus
from app.domain.errors import DomainValidationError, ImmutableArtifactError, InvariantViolationError


@dataclass
class SpecificationVersion:
    """Versioned artifact containing structured engineering specification content."""
    specification_id: UUID
    version_number: int
    structured_content: Dict[str, Any]
    id: UUID = field(default_factory=uuid4)
    is_approved: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if self.version_number < 1:
            raise DomainValidationError("Specification version number must be >= 1")
        if not self.structured_content:
            raise DomainValidationError("Specification structured content cannot be empty")
        if self.created_at.tzinfo is None:
            raise DomainValidationError("Timestamps must be timezone-aware UTC")

    def update_content(self, new_content: Dict[str, Any]) -> None:
        """Modify specification content; forbidden once approved."""
        if self.is_approved:
            raise ImmutableArtifactError(f"Specification version {self.version_number} is approved and locked")
        if not new_content:
            raise DomainValidationError("Specification content cannot be empty")
        self.structured_content = new_content

    def mark_approved(self) -> None:
        """Freeze this version upon formal approval."""
        self.is_approved = True


@dataclass
class Specification:
    """Specification aggregate root."""
    project_id: UUID
    requirement_id: UUID
    id: UUID = field(default_factory=uuid4)
    status: SpecificationStatus = SpecificationStatus.DRAFT
    current_version_number: int = 1
    versions: List[SpecificationVersion] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if self.current_version_number < 1:
            raise DomainValidationError("Specification version must be >= 1")
        if self.created_at.tzinfo is None or self.updated_at.tzinfo is None:
            raise DomainValidationError("Timestamps must be timezone-aware UTC")

    def get_version(self, version_number: int) -> Optional[SpecificationVersion]:
        """Retrieve a specific version."""
        for v in self.versions:
            if v.version_number == version_number:
                return v
        return None

    def get_current_version(self) -> Optional[SpecificationVersion]:
        """Retrieve current version."""
        return self.get_version(self.current_version_number)

    def add_version(self, structured_content: Dict[str, Any]) -> SpecificationVersion:
        """Create a new specification revision."""
        new_version_num = len(self.versions) + 1
        ver = SpecificationVersion(
            specification_id=self.id,
            version_number=new_version_num,
            structured_content=structured_content,
        )
        self.versions.append(ver)
        self.current_version_number = new_version_num
        self.status = SpecificationStatus.DRAFT
        self.updated_at = datetime.now(timezone.utc)
        return ver

    def approve(self, version_number: int) -> None:
        """Approve a specific version and lock it."""
        target_version = self.get_version(version_number)
        if not target_version:
            raise InvariantViolationError(f"Version {version_number} does not exist on specification")
        target_version.mark_approved()
        self.status = SpecificationStatus.APPROVED
        self.updated_at = datetime.now(timezone.utc)

    def reject(self, reason: str = "") -> None:
        """Reject specification."""
        self.status = SpecificationStatus.REJECTED
        self.updated_at = datetime.now(timezone.utc)

    def request_clarification(self) -> None:
        """Transition to clarification required."""
        self.status = SpecificationStatus.CLARIFICATION_REQUIRED
        self.updated_at = datetime.now(timezone.utc)

    def submit_for_review(self) -> None:
        """Transition specification to READY_FOR_REVIEW."""
        if not self.versions:
            raise InvariantViolationError("Cannot submit empty specification for review")
        self.status = SpecificationStatus.READY_FOR_REVIEW
        self.updated_at = datetime.now(timezone.utc)

    def is_construction_authorized(self) -> bool:
        """Rule: Only an APPROVED specification authorizes material workflow construction."""
        return self.status == SpecificationStatus.APPROVED
