"""RepairAttempt SQLAlchemy ORM model."""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID, uuid4
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UUID as SQLUUID
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON
from app.db.base import Base

JSONType = JSON().with_variant(JSONB, "postgresql")


class RepairAttemptModel(Base):
    """Persistence model for RepairAttempt entity."""

    __tablename__ = "repair_attempts"
    __table_args__ = (
        Index("idx_repair_attempts_workflow", "workflow_id"),
    )

    id: Mapped[UUID] = mapped_column(SQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    workflow_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("workflows.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    target_version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    failure_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("failure_records.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    diagnostic_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("diagnostic_findings.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    proposed_change: Mapped[Dict[str, Any]] = mapped_column(JSONType, nullable=False)
    risk: Mapped[str] = mapped_column(String(50), nullable=False, default="LOW")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PROPOSED")
    initiated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    workflow: Mapped["WorkflowModel"] = relationship("WorkflowModel")
    failure: Mapped["FailureRecordModel"] = relationship("FailureRecordModel", back_populates="repairs")
    diagnostic: Mapped["DiagnosticFindingModel"] = relationship("DiagnosticFindingModel", back_populates="repairs")
