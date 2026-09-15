"""Workflow and WorkflowVersion SQLAlchemy ORM models."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, UUID as SQLUUID
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON
from app.db.base import Base

JSONType = JSON().with_variant(JSONB, "postgresql")


class WorkflowModel(Base):
    """Persistence model for Workflow aggregate root."""

    __tablename__ = "workflows"

    id: Mapped[UUID] = mapped_column(SQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    environment: Mapped[str] = mapped_column(String(50), nullable=False, default="development")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="DRAFT")
    current_version_id: Mapped[Optional[UUID]] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("workflow_versions.id", ondelete="SET NULL", use_alter=True, name="fk_workflows_current_version"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    project: Mapped["ProjectModel"] = relationship("ProjectModel", back_populates="workflows")
    versions: Mapped[List["WorkflowVersionModel"]] = relationship(
        "WorkflowVersionModel",
        back_populates="workflow",
        foreign_keys="WorkflowVersionModel.workflow_id",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="WorkflowVersionModel.version_number",
    )
    current_version: Mapped[Optional["WorkflowVersionModel"]] = relationship(
        "WorkflowVersionModel",
        foreign_keys=[current_version_id],
        post_update=True,
    )
    executions: Mapped[List["ExecutionModel"]] = relationship(
        "ExecutionModel",
        back_populates="workflow",
        passive_deletes="all",
    )
    deployments: Mapped[List["DeploymentModel"]] = relationship(
        "DeploymentModel",
        back_populates="workflow",
        passive_deletes="all",
    )


class WorkflowVersionModel(Base):
    """Persistence model for WorkflowVersion entity."""

    __tablename__ = "workflow_versions"
    __table_args__ = (
        UniqueConstraint("workflow_id", "version_number", name="uq_workflow_versions_number"),
        Index("idx_wf_versions_lookup", "workflow_id", "version_number"),
    )

    id: Mapped[UUID] = mapped_column(SQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    workflow_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("workflows.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    specification_version_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("specification_versions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    definition: Mapped[Dict[str, Any]] = mapped_column(JSONType, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="DRAFT")
    change_reason: Mapped[str] = mapped_column(Text, nullable=False, default="Initial version")
    created_by: Mapped[str] = mapped_column(String(100), nullable=False, default="agent")
    provider_version_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    workflow: Mapped["WorkflowModel"] = relationship(
        "WorkflowModel",
        back_populates="versions",
        foreign_keys=[workflow_id],
    )
    specification_version: Mapped["SpecificationVersionModel"] = relationship(
        "SpecificationVersionModel",
        back_populates="workflow_versions",
    )
    executions: Mapped[List["ExecutionModel"]] = relationship(
        "ExecutionModel",
        back_populates="workflow_version",
        passive_deletes="all",
    )
    deployments: Mapped[List["DeploymentModel"]] = relationship(
        "DeploymentModel",
        back_populates="workflow_version",
        passive_deletes="all",
    )
