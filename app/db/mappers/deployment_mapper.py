"""Deployment domain <-> persistence mapper."""

from app.db.mappers.helpers import ensure_utc
from app.db.models.deployment import DeploymentModel
from app.domain.enums import DeploymentStatus
from app.domain.models.deployment import Deployment


def deployment_to_domain(model: DeploymentModel) -> Deployment:
    """Map DeploymentModel to domain Deployment entity."""
    return Deployment(
        id=model.id,
        workflow_id=model.workflow_id,
        workflow_version_id=model.workflow_version_id,
        workflow_version_number=model.workflow_version_number,
        target_environment=model.target_environment,
        deployed_by=model.deployed_by,
        approval_id=model.approval_id,
        status=DeploymentStatus(model.status),
        deployed_at=ensure_utc(model.deployed_at),
        error_message=model.error_message,
    )


def deployment_to_model(entity: Deployment) -> DeploymentModel:
    """Map domain Deployment entity to DeploymentModel."""
    return DeploymentModel(
        id=entity.id,
        workflow_id=entity.workflow_id,
        workflow_version_id=entity.workflow_version_id,
        workflow_version_number=entity.workflow_version_number,
        target_environment=entity.target_environment,
        deployed_by=entity.deployed_by,
        approval_id=entity.approval_id,
        status=entity.status.value,
        deployed_at=ensure_utc(entity.deployed_at),
        error_message=entity.error_message,
    )
