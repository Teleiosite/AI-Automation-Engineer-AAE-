"""Approval repository adapter with atomic single-winner consumption."""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID
from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session
from app.db.mappers.approval_mapper import approval_to_domain, approval_to_model
from app.db.models.approval import ApprovalModel
from app.domain.enums import ApprovalDecision, ApprovalStatus, ApprovalTargetType
from app.domain.errors import StaleApprovalError
from app.domain.models.approval import Approval


class ApprovalRepository:
    """Repository managing Approval persistence and atomic single-use consumption."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, approval_id: UUID) -> Optional[Approval]:
        """Fetch approval record by UUID."""
        stmt = select(ApprovalModel).where(ApprovalModel.id == approval_id)
        model = self._session.execute(stmt).scalar_one_or_none()
        return approval_to_domain(model) if model else None

    def get_active_for_target(
        self,
        target_type: ApprovalTargetType,
        target_id: UUID,
        target_version: int,
        environment: Optional[str] = None,
        action: str = "deploy",
    ) -> Optional[Approval]:
        """
        Find an active, approved, non-expired approval for the target artifact, version, and environment.
        """
        now = datetime.now(timezone.utc)
        conditions = [
            ApprovalModel.target_type == target_type.value,
            ApprovalModel.target_id == target_id,
            ApprovalModel.target_version == target_version,
            ApprovalModel.action == action,
            ApprovalModel.decision == ApprovalDecision.APPROVED.value,
            ApprovalModel.status == ApprovalStatus.ACTIVE.value,
            or_(
                ApprovalModel.expires_at.is_(None),
                ApprovalModel.expires_at > now,
            ),
        ]
        if environment is not None:
            conditions.append(
                or_(
                    ApprovalModel.environment.is_(None),
                    ApprovalModel.environment == environment,
                )
            )

        stmt = select(ApprovalModel).where(*conditions).order_by(ApprovalModel.decided_at.desc())
        model = self._session.execute(stmt).scalars().first()
        return approval_to_domain(model) if model else None

    def save(self, approval: Approval) -> Approval:
        """Persist or update Approval entity."""
        stmt = select(ApprovalModel).where(ApprovalModel.id == approval.id)
        model = self._session.execute(stmt).scalar_one_or_none()

        if model:
            model.decision = approval.decision.value
            model.status = approval.status.value
            model.decided_at = approval.decided_at
            model.expires_at = approval.expires_at
            model.consumed_at = approval.consumed_at
            model.consumed_by_action_id = approval.consumed_by_action_id
            model.comments = approval.comments
        else:
            model = approval_to_model(approval)
            self._session.add(model)

        self._session.flush()
        return approval_to_domain(model)

    def consume_atomic(self, approval_id: UUID, action_id: UUID) -> Approval:
        """
        Atomically consume an active approval record in a single SQL operation.
        Guarantees single-winner consumption under high concurrency.
        Raises StaleApprovalError if the approval was already consumed, expired, or not active.
        """
        now = datetime.now(timezone.utc)
        stmt = (
            update(ApprovalModel)
            .where(
                ApprovalModel.id == approval_id,
                ApprovalModel.status == ApprovalStatus.ACTIVE.value,
                ApprovalModel.decision == ApprovalDecision.APPROVED.value,
                or_(
                    ApprovalModel.expires_at.is_(None),
                    ApprovalModel.expires_at > now,
                ),
            )
            .values(
                status=ApprovalStatus.CONSUMED.value,
                consumed_at=now,
                consumed_by_action_id=action_id,
            )
        )
        result = self._session.execute(stmt)
        if result.rowcount != 1:
            raise StaleApprovalError(
                f"Approval '{approval_id}' could not be consumed: already consumed, expired, or inactive"
            )

        self._session.flush()
        updated_approval = self.get(approval_id)
        assert updated_approval is not None
        return updated_approval
