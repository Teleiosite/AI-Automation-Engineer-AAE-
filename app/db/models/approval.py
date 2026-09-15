"""Approval SQLAlchemy ORM model."""

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4
from sqlalchemy import DateTime, Index, Integer, String, Text, UUID as SQLUUID
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class ApprovalModel(Base):
    """Persistence model for Approval entity with single-use consumption state."""

    __tablename__ = "approvals"
    __table_args__ = (
        Index("idx_approvals_target", "target_type", "target_id", "target_version", "status"),
        Index("idx_approvals_status_expiry", "status", "expires_at"),
    )

    id: Mapped[UUID] = mapped_column(SQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    target_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_id: Mapped[UUID] = mapped_column(SQLUUID(as_uuid=True), nullable=False, index=True)
    target_version: Mapped[int] = mapped_column(Integer, nullable=False)
    actor: Mapped[str] = mapped_column(String(255), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False, default="deploy")
    environment: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    decision: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING", index=True)
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    consumed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    consumed_by_action_id: Mapped[Optional[UUID]] = mapped_column(SQLUUID(as_uuid=True), nullable=True)
    comments: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
