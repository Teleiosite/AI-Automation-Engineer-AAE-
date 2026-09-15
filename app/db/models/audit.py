"""AuditEvent SQLAlchemy ORM model."""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID, uuid4
from sqlalchemy import DateTime, Index, String, UUID as SQLUUID
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON
from app.db.base import Base

JSONType = JSON().with_variant(JSONB, "postgresql")


class AuditEventModel(Base):
    """
    Persistence model for AuditEvent entity.
    Append-only governance record storing pre-sanitized event metadata.
    """

    __tablename__ = "audit_events"
    __table_args__ = (
        Index("idx_audit_events_timestamp", "timestamp"),
        Index("idx_audit_events_target", "target_type", "target_id"),
        Index("idx_audit_events_correlation", "correlation_id"),
    )

    id: Mapped[UUID] = mapped_column(SQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    actor: Mapped[str] = mapped_column(String(255), nullable=False)
    target_type: Mapped[str] = mapped_column(String(100), nullable=False)
    target_id: Mapped[str] = mapped_column(String(255), nullable=False)
    correlation_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    outcome: Mapped[str] = mapped_column(String(50), nullable=False, default="SUCCESS")
    event_metadata: Mapped[Dict[str, Any]] = mapped_column("metadata", JSONType, nullable=False, default=dict)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
