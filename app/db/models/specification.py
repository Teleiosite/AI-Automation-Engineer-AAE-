"""Specification and SpecificationVersion SQLAlchemy ORM models."""

from datetime import datetime, timezone
from typing import Any, Dict, List
from uuid import UUID, uuid4
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, UUID as SQLUUID
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON
from app.db.base import Base

JSONType = JSON().with_variant(JSONB, "postgresql")


class SpecificationModel(Base):
    """Persistence model for Specification aggregate root."""

    __tablename__ = "specifications"

    id: Mapped[UUID] = mapped_column(SQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    requirement_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("requirements.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="DRAFT")
    current_version_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
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
    project: Mapped["ProjectModel"] = relationship("ProjectModel", back_populates="specifications")
    requirement: Mapped["RequirementModel"] = relationship("RequirementModel", back_populates="specifications")
    versions: Mapped[List["SpecificationVersionModel"]] = relationship(
        "SpecificationVersionModel",
        back_populates="specification",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="SpecificationVersionModel.version_number",
    )


class SpecificationVersionModel(Base):
    """Persistence model for SpecificationVersion entity."""

    __tablename__ = "specification_versions"
    __table_args__ = (
        UniqueConstraint("specification_id", "version_number", name="uq_specification_versions_number"),
        Index("idx_spec_versions_lookup", "specification_id", "version_number"),
    )

    id: Mapped[UUID] = mapped_column(SQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    specification_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("specifications.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    structured_content: Mapped[Dict[str, Any]] = mapped_column(JSONType, nullable=False)
    is_approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    specification: Mapped["SpecificationModel"] = relationship("SpecificationModel", back_populates="versions")
    workflow_versions: Mapped[List["WorkflowVersionModel"]] = relationship(
        "WorkflowVersionModel",
        back_populates="specification_version",
        passive_deletes="all",
    )
