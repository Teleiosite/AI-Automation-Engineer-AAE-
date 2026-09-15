"""Approval domain <-> persistence mapper."""

from app.db.mappers.helpers import ensure_utc
from app.db.models.approval import ApprovalModel
from app.domain.enums import ApprovalDecision, ApprovalStatus, ApprovalTargetType
from app.domain.models.approval import Approval


def approval_to_domain(model: ApprovalModel) -> Approval:
    """Map ApprovalModel to domain Approval entity."""
    return Approval(
        id=model.id,
        target_type=ApprovalTargetType(model.target_type),
        target_id=model.target_id,
        target_version=model.target_version,
        actor=model.actor,
        action=model.action,
        environment=model.environment,
        decision=ApprovalDecision(model.decision),
        status=ApprovalStatus(model.status),
        decided_at=ensure_utc(model.decided_at),
        expires_at=ensure_utc(model.expires_at),
        consumed_at=ensure_utc(model.consumed_at),
        consumed_by_action_id=model.consumed_by_action_id,
        comments=model.comments,
    )


def approval_to_model(entity: Approval) -> ApprovalModel:
    """Map domain Approval entity to ApprovalModel."""
    return ApprovalModel(
        id=entity.id,
        target_type=entity.target_type.value,
        target_id=entity.target_id,
        target_version=entity.target_version,
        actor=entity.actor,
        action=entity.action,
        environment=entity.environment,
        decision=entity.decision.value,
        status=entity.status.value,
        decided_at=ensure_utc(entity.decided_at),
        expires_at=ensure_utc(entity.expires_at),
        consumed_at=ensure_utc(entity.consumed_at),
        consumed_by_action_id=entity.consumed_by_action_id,
        comments=entity.comments,
    )
