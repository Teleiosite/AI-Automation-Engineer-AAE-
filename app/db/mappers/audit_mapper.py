"""AuditEvent domain <-> persistence mapper."""

from app.db.mappers.helpers import ensure_utc
from app.db.models.audit import AuditEventModel
from app.domain.models.audit import AuditEvent


def audit_event_to_domain(model: AuditEventModel) -> AuditEvent:
    """Map AuditEventModel to domain AuditEvent entity."""
    return AuditEvent(
        id=model.id,
        event_type=model.event_type,
        actor=model.actor,
        target_type=model.target_type,
        target_id=model.target_id,
        correlation_id=model.correlation_id,
        outcome=model.outcome,
        metadata=dict(model.event_metadata or {}),
        timestamp=ensure_utc(model.timestamp),
    )


def audit_event_to_model(entity: AuditEvent) -> AuditEventModel:
    """Map domain AuditEvent entity to AuditEventModel."""
    return AuditEventModel(
        id=entity.id,
        event_type=entity.event_type,
        actor=entity.actor,
        target_type=entity.target_type,
        target_id=entity.target_id,
        correlation_id=entity.correlation_id,
        outcome=entity.outcome,
        event_metadata=dict(entity.metadata or {}),
        timestamp=ensure_utc(entity.timestamp),
    )
