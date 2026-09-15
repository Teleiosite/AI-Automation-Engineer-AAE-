"""Deployment repository adapter."""

from typing import List, Optional
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db.mappers.deployment_mapper import deployment_to_domain, deployment_to_model
from app.db.models.deployment import DeploymentModel
from app.domain.models.deployment import Deployment


class DeploymentRepository:
    """Repository managing Deployment aggregate persistence."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, deployment_id: UUID) -> Optional[Deployment]:
        """Fetch deployment by UUID."""
        stmt = select(DeploymentModel).where(DeploymentModel.id == deployment_id)
        model = self._session.execute(stmt).scalar_one_or_none()
        return deployment_to_domain(model) if model else None

    def save(self, deployment: Deployment) -> Deployment:
        """Persist or update Deployment entity."""
        stmt = select(DeploymentModel).where(DeploymentModel.id == deployment.id)
        model = self._session.execute(stmt).scalar_one_or_none()

        if model:
            model.status = deployment.status.value
            model.approval_id = deployment.approval_id
            model.deployed_at = deployment.deployed_at
            model.error_message = deployment.error_message
        else:
            model = deployment_to_model(deployment)
            self._session.add(model)

        self._session.flush()
        return deployment_to_domain(model)

    def list_for_workflow(self, workflow_id: UUID) -> List[Deployment]:
        """List deployments for a workflow ordered by creation desc."""
        stmt = (
            select(DeploymentModel)
            .where(DeploymentModel.workflow_id == workflow_id)
            .order_by(DeploymentModel.deployed_at.desc())
        )
        models = self._session.execute(stmt).scalars().all()
        return [deployment_to_domain(m) for m in models]
