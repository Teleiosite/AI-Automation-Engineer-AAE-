"""Requirement and RequirementItem SQLAlchemy ORM models."""

from datetime import datetime, timezone
from typing import Any, List, Optional
from uuid import UUID, uuid4
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UUID as SQLUUID
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON
from app.db.base import Base

JSONType = JSON().with_variant(JSONB, "postgresql")


class RequirementModel(Base):
    """Persistence model for Requirement aggregate."""

    __tablename__ = "requirements"

    id: Mapped[UUID] = mapped_column(SQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    original_request: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(String(100), nullable=False, default="user")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    assumptions: Mapped[List[Any]] = mapped_column(JSONType, nullable=False, default=list)
    ambiguities: Mapped[List[Any]] = mapped_column(JSONType, nullable=False, default=list)
    conflicts: Mapped[List[Any]] = mapped_column(JSONType, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    project: Mapped["ProjectModel"] = relationship("ProjectModel", back_populates="requirements")
    items: Mapped[List["RequirementItemModel"]] = relationship(
        "RequirementItemModel",
        back_populates="requirement",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    specifications: Mapped[List["SpecificationModel"]] = relationship(
        "SpecificationModel",
        back_populates="requirement",
        passive_deletes="all",
    )


class RequirementItemModel(Base):
    """Persistence model for RequirementItem value object."""

    __tablename__ = "requirement_items"

    id: Mapped[UUID] = mapped_column(SQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    requirement_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("requirements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[str] = mapped_column(String(50), nullable=False)
    risk: Mapped[str] = mapped_column(String(50), nullable=False, default="LOW")
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    requirement: Mapped["RequirementModel"] = relationship("RequirementModel", back_populates="items")
