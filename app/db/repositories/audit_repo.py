"""AuditEvent append-only repository adapter."""

from typing import List, Optional
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db.mappers.audit_mapper import audit_event_to_domain, audit_event_to_model
from app.db.models.audit import AuditEventModel
from app.domain.models.audit import AuditEvent


class AuditRepository:
    """
    Append-only repository managing AuditEvent persistence.
    Exposes no update or delete operations, preserving governance log integrity.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def append(self, event: AuditEvent) -> AuditEvent:
        """Append an immutable audit event record."""
        model = audit_event_to_model(event)
        self._session.add(model)
        self._session.flush()
        return audit_event_to_domain(model)

    def get(self, event_id: UUID) -> Optional[AuditEvent]:
        """Fetch audit event by UUID."""
        stmt = select(AuditEventModel).where(AuditEventModel.id == event_id)
        model = self._session.execute(stmt).scalar_one_or_none()
        return audit_event_to_domain(model) if model else None

    def list_for_target(self, target_type: str, target_id: str) -> List[AuditEvent]:
        """Query audit log by target entity."""
        stmt = (
            select(AuditEventModel)
            .where(
                AuditEventModel.target_type == target_type,
                AuditEventModel.target_id == target_id,
            )
            .order_by(AuditEventModel.timestamp.asc())
        )
        models = self._session.execute(stmt).scalars().all()
        return [audit_event_to_domain(m) for m in models]

    def list_recent(self, limit: int = 100) -> List[AuditEvent]:
        """Query recent audit events ordered chronologically descending."""
        stmt = select(AuditEventModel).order_by(AuditEventModel.timestamp.desc()).limit(limit)
        models = self._session.execute(stmt).scalars().all()
        return [audit_event_to_domain(m) for m in models]
