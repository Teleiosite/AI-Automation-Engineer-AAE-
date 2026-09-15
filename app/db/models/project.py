"""Project SQLAlchemy ORM model."""

from datetime import datetime, timezone
from uuid import UUID, uuid4
from sqlalchemy import Boolean, DateTime, String, Text, UUID as SQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class ProjectModel(Base):
    """Persistence model for Project aggregate."""

    __tablename__ = "projects"

    id: Mapped[UUID] = mapped_column(SQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    requirements: Mapped[list["RequirementModel"]] = relationship(
        "RequirementModel",
        back_populates="project",
        passive_deletes="all",
    )
    specifications: Mapped[list["SpecificationModel"]] = relationship(
        "SpecificationModel",
        back_populates="project",
        passive_deletes="all",
    )
    workflows: Mapped[list["WorkflowModel"]] = relationship(
        "WorkflowModel",
        back_populates="project",
        passive_deletes="all",
    )
