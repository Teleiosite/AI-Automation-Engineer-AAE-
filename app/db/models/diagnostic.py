"""FailureRecord and DiagnosticFinding SQLAlchemy ORM models."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4
from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UUID as SQLUUID
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON
from app.db.base import Base

JSONType = JSON().with_variant(JSONB, "postgresql")


class FailureRecordModel(Base):
    """Persistence model for FailureRecord value object/entity."""

    __tablename__ = "failure_records"
    __table_args__ = (
        Index("idx_failure_records_execution", "execution_id"),
    )

    id: Mapped[UUID] = mapped_column(SQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    execution_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("executions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(String(50), nullable=False)
    failed_component: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    technical_details: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONType, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    execution: Mapped["ExecutionModel"] = relationship("ExecutionModel", back_populates="failure_records")
    findings: Mapped[List["DiagnosticFindingModel"]] = relationship(
        "DiagnosticFindingModel",
        back_populates="failure",
        passive_deletes="all",
    )
    repairs: Mapped[List["RepairAttemptModel"]] = relationship(
        "RepairAttemptModel",
        back_populates="failure",
        passive_deletes="all",
    )


class DiagnosticFindingModel(Base):
    """Persistence model for DiagnosticFinding value object/entity."""

    __tablename__ = "diagnostic_findings"
    __table_args__ = (
        Index("idx_diagnostic_findings_failure", "failure_id"),
    )

    id: Mapped[UUID] = mapped_column(SQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    failure_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("failure_records.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    likely_cause: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[str] = mapped_column(String(50), nullable=False)
    recommended_action: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    failure: Mapped["FailureRecordModel"] = relationship("FailureRecordModel", back_populates="findings")
    repairs: Mapped[List["RepairAttemptModel"]] = relationship(
        "RepairAttemptModel",
        back_populates="diagnostic",
        passive_deletes="all",
    )
