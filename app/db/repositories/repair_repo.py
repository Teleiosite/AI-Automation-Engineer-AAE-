"""RepairAttempt repository adapter."""

from typing import List, Optional
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db.mappers.repair_mapper import repair_attempt_to_domain, repair_attempt_to_model
from app.db.models.repair import RepairAttemptModel
from app.domain.models.repair import RepairAttempt


class RepairRepository:
    """Repository managing RepairAttempt persistence."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, repair_id: UUID) -> Optional[RepairAttempt]:
        """Fetch repair attempt by UUID."""
        stmt = select(RepairAttemptModel).where(RepairAttemptModel.id == repair_id)
        model = self._session.execute(stmt).scalar_one_or_none()
        return repair_attempt_to_domain(model) if model else None

    def save(self, repair: RepairAttempt) -> RepairAttempt:
        """Persist or update RepairAttempt entity."""
        stmt = select(RepairAttemptModel).where(RepairAttemptModel.id == repair.id)
        model = self._session.execute(stmt).scalar_one_or_none()

        if model:
            model.status = repair.status
            model.completed_at = repair.completed_at
        else:
            model = repair_attempt_to_model(repair)
            self._session.add(model)

        self._session.flush()
        return repair_attempt_to_domain(model)

    def list_for_workflow(self, workflow_id: UUID) -> List[RepairAttempt]:
        """List repair attempts for a workflow."""
        stmt = (
            select(RepairAttemptModel)
            .where(RepairAttemptModel.workflow_id == workflow_id)
            .order_by(RepairAttemptModel.initiated_at.desc())
        )
        models = self._session.execute(stmt).scalars().all()
        return [repair_attempt_to_domain(m) for m in models]
