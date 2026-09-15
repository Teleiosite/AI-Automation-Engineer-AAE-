"""Approval domain entity with deterministic single-use replay protection."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4
from app.domain.enums import ApprovalDecision, ApprovalStatus, ApprovalTargetType
from app.domain.errors import DomainValidationError, StaleApprovalError


@dataclass
class Approval:
    """
    Authoritative approval record enforcing strict single-use consumption and replay defense.
    An approval granted for (artifact, version A, environment E) can never authorize version B,
    nor can a consumed approval be replayed for subsequent executions.
    """
    target_type: ApprovalTargetType
    target_id: UUID
    target_version: int
    actor: str
    action: str = "deploy"
    id: UUID = field(default_factory=uuid4)
    environment: Optional[str] = None
    decision: ApprovalDecision = ApprovalDecision.PENDING
    status: ApprovalStatus = ApprovalStatus.PENDING
    decided_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    consumed_at: Optional[datetime] = None
    consumed_by_action_id: Optional[UUID] = None
    comments: Optional[str] = None

    def __post_init__(self) -> None:
        if self.target_version < 1:
            raise DomainValidationError("Target version must be >= 1")
        if not self.actor or not self.actor.strip():
            raise DomainValidationError("Approval actor cannot be empty")
        if self.decided_at is not None and self.decided_at.tzinfo is None:
            raise DomainValidationError("Timestamps must be timezone-aware UTC")
        if self.expires_at is not None and self.expires_at.tzinfo is None:
            raise DomainValidationError("Timestamps must be timezone-aware UTC")
        if self.consumed_at is not None and self.consumed_at.tzinfo is None:
            raise DomainValidationError("Timestamps must be timezone-aware UTC")

    def approve(self, comments: Optional[str] = None, expires_at: Optional[datetime] = None) -> None:
        """Record formal approval and transition to ACTIVE."""
        self.decision = ApprovalDecision.APPROVED
        self.status = ApprovalStatus.ACTIVE
        self.decided_at = datetime.now(timezone.utc)
        self.comments = comments
        self.expires_at = expires_at

    def reject(self, comments: Optional[str] = None) -> None:
        """Record formal rejection."""
        self.decision = ApprovalDecision.REJECTED
        self.status = ApprovalStatus.REVOKED
        self.decided_at = datetime.now(timezone.utc)
        self.comments = comments

    def is_valid_for(
        self,
        target_type: ApprovalTargetType,
        target_id: UUID,
        target_version: int,
        environment: Optional[str] = None,
        action: Optional[str] = None,
    ) -> bool:
        """
        Verify that this approval strictly matches the target artifact, version, and environment,
        and is currently ACTIVE and not expired.
        """
        if self.decision != ApprovalDecision.APPROVED or self.status != ApprovalStatus.ACTIVE:
            return False

        if self.expires_at and datetime.now(timezone.utc) > self.expires_at:
            return False

        if self.target_type != target_type:
            return False

        if self.target_id != target_id:
            return False

        if self.target_version != target_version:
            return False

        if self.environment is not None and environment is not None and self.environment != environment:
            return False

        if action is not None and self.action != action:
            return False

        return True

    def consume(self, action_id: UUID) -> None:
        """
        Deterministically consume this approval for an authorized action.
        Prevents approval replay: An approval can only be consumed once.
        """
        if self.status == ApprovalStatus.CONSUMED:
            raise StaleApprovalError(
                f"Approval '{self.id}' was already consumed by action '{self.consumed_by_action_id}'"
            )

        if self.status != ApprovalStatus.ACTIVE or self.decision != ApprovalDecision.APPROVED:
            raise StaleApprovalError(f"Approval '{self.id}' is in status '{self.status.value}' and cannot be consumed")

        if self.expires_at and datetime.now(timezone.utc) > self.expires_at:
            self.status = ApprovalStatus.EXPIRED
            raise StaleApprovalError(f"Approval '{self.id}' expired at {self.expires_at}")

        self.status = ApprovalStatus.CONSUMED
        self.consumed_at = datetime.now(timezone.utc)
        self.consumed_by_action_id = action_id

    def supersede(self) -> None:
        """Mark approval as superseded by a newer version or change."""
        self.status = ApprovalStatus.SUPERSEDED

    def revoke(self, reason: str = "") -> None:
        """Explicitly revoke approval."""
        self.status = ApprovalStatus.REVOKED
        if reason:
            self.comments = f"Revoked: {reason}"
