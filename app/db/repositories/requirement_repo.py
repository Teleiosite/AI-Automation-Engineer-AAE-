"""Requirement repository adapter."""

from typing import Optional
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from app.db.mappers.requirement_mapper import (
    requirement_item_to_model,
    requirement_to_domain,
    requirement_to_model,
)
from app.db.models.requirement import RequirementModel
from app.domain.models.requirement import Requirement


class RequirementRepository:
    """Repository managing Requirement aggregate persistence."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, requirement_id: UUID) -> Optional[Requirement]:
        """Fetch requirement by UUID with its child items."""
        stmt = (
            select(RequirementModel)
            .options(selectinload(RequirementModel.items))
            .where(RequirementModel.id == requirement_id)
        )
        model = self._session.execute(stmt).scalar_one_or_none()
        return requirement_to_domain(model) if model else None

    def save(self, requirement: Requirement) -> Requirement:
        """Persist or update Requirement aggregate."""
        stmt = (
            select(RequirementModel)
            .options(selectinload(RequirementModel.items))
            .where(RequirementModel.id == requirement.id)
        )
        model = self._session.execute(stmt).scalar_one_or_none()

        if model:
            model.original_request = requirement.original_request
            model.created_by = requirement.created_by
            model.version = requirement.version
            model.assumptions = list(requirement.assumptions)
            model.ambiguities = list(requirement.ambiguities)
            model.conflicts = list(requirement.conflicts)

            # Sync items (cascade delete-orphan handles removals)
            model.items = [requirement_item_to_model(item, requirement.id) for item in requirement.items]
        else:
            model = requirement_to_model(requirement)
            self._session.add(model)

        self._session.flush()
        return requirement_to_domain(model)
