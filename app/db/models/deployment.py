"""Deployment SQLAlchemy ORM model."""

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UUID as SQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class DeploymentModel(Base):
    """Persistence model for Deployment entity."""

    __tablename__ = "deployments"
    __table_args__ = (
        Index("idx_deployments_workflow", "workflow_id", "workflow_version_id"),
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
    workflow_version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    target_environment: Mapped[str] = mapped_column(String(50), nullable=False)
    deployed_by: Mapped[str] = mapped_column(String(255), nullable=False)
    approval_id: Mapped[Optional[UUID]] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("approvals.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING")
    deployed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    workflow: Mapped["WorkflowModel"] = relationship("WorkflowModel", back_populates="deployments")
    workflow_version: Mapped["WorkflowVersionModel"] = relationship("WorkflowVersionModel", back_populates="deployments")
    approval: Mapped[Optional["ApprovalModel"]] = relationship("ApprovalModel")
