"""Execution SQLAlchemy ORM model with embedded ExecutionResult value object."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4
from sqlalchemy import DateTime, Float, ForeignKey, Index, String, Text, UUID as SQLUUID
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON
from app.db.base import Base

JSONType = JSON().with_variant(JSONB, "postgresql")


class ExecutionModel(Base):
    """
    Persistence model for Execution aggregate.
    Embeds ExecutionResult value object directly to preserve atomic read/write.
    """

    __tablename__ = "executions"
    __table_args__ = (
        Index("idx_executions_workflow", "workflow_id", "workflow_version_id"),
        Index("idx_executions_correlation_id", "correlation_id"),
    )

    id: Mapped[UUID] = mapped_column(SQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    workflow_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("workflows.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    workflow_version_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("workflow_versions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="QUEUED")
    trigger_type: Mapped[str] = mapped_column(String(50), nullable=False, default="MANUAL")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    correlation_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Embedded ExecutionResult value object fields
    result_technical_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    result_semantic_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    result_duration_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    result_output_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONType, nullable=True)
    result_error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    result_error_details: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONType, nullable=True)

    # Relationships
    workflow: Mapped["WorkflowModel"] = relationship("WorkflowModel", back_populates="executions")
    workflow_version: Mapped["WorkflowVersionModel"] = relationship("WorkflowVersionModel", back_populates="executions")
    failure_records: Mapped[List["FailureRecordModel"]] = relationship(
        "FailureRecordModel",
        back_populates="execution",
        passive_deletes="all",
    )
