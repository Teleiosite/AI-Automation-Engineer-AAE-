"""RepairAttempt domain <-> persistence mapper."""

from app.db.mappers.helpers import ensure_utc
from app.db.models.repair import RepairAttemptModel
from app.domain.enums import RiskLevel
from app.domain.models.repair import RepairAttempt


def repair_attempt_to_domain(model: RepairAttemptModel) -> RepairAttempt:
    """Map RepairAttemptModel to domain RepairAttempt entity."""
    return RepairAttempt(
        id=model.id,
        workflow_id=model.workflow_id,
        target_version_number=model.target_version_number,
        failure_id=model.failure_id,
        diagnostic_id=model.diagnostic_id,
        proposed_change=dict(model.proposed_change or {}),
        risk=RiskLevel(model.risk),
        status=model.status,
        initiated_at=ensure_utc(model.initiated_at),
        completed_at=ensure_utc(model.completed_at),
    )


def repair_attempt_to_model(entity: RepairAttempt) -> RepairAttemptModel:
    """Map domain RepairAttempt entity to RepairAttemptModel."""
    return RepairAttemptModel(
        id=entity.id,
        workflow_id=entity.workflow_id,
        target_version_number=entity.target_version_number,
        failure_id=entity.failure_id,
        diagnostic_id=entity.diagnostic_id,
        proposed_change=dict(entity.proposed_change or {}),
        risk=entity.risk.value,
        status=entity.status,
        initiated_at=ensure_utc(entity.initiated_at),
        completed_at=ensure_utc(entity.completed_at),
    )
