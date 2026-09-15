"""Execution repository adapter."""

from typing import List, Optional
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db.mappers.execution_mapper import execution_to_domain, execution_to_model
from app.db.models.execution import ExecutionModel
from app.domain.models.execution import Execution


class ExecutionRepository:
    """Repository managing Execution aggregate persistence."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, execution_id: UUID) -> Optional[Execution]:
        """Fetch execution run by UUID."""
        stmt = select(ExecutionModel).where(ExecutionModel.id == execution_id)
        model = self._session.execute(stmt).scalar_one_or_none()
        return execution_to_domain(model) if model else None

    def save(self, execution: Execution) -> Execution:
        """Persist or update Execution aggregate."""
        stmt = select(ExecutionModel).where(ExecutionModel.id == execution.id)
        model = self._session.execute(stmt).scalar_one_or_none()

        if model:
            model.status = execution.status.value
            model.trigger_type = execution.trigger_type.value
            model.finished_at = execution.finished_at
            model.correlation_id = execution.correlation_id
            if execution.result is not None:
                model.result_technical_status = execution.result.technical_status.value
                model.result_semantic_status = execution.result.semantic_status.value
                model.result_duration_ms = execution.result.duration_ms
                model.result_output_data = execution.result.output_data
                model.result_error_message = execution.result.error_message
                model.result_error_details = execution.result.error_details
        else:
            model = execution_to_model(execution)
            self._session.add(model)

        self._session.flush()
        return execution_to_domain(model)

    def list_for_workflow(self, workflow_id: UUID) -> List[Execution]:
        """List execution runs for a workflow ordered by start time desc."""
        stmt = (
            select(ExecutionModel)
            .where(ExecutionModel.workflow_id == workflow_id)
            .order_by(ExecutionModel.started_at.desc())
        )
        models = self._session.execute(stmt).scalars().all()
        return [execution_to_domain(m) for m in models]
