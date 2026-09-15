"""Workflow and WorkflowVersion domain <-> persistence mappers."""

from app.db.mappers.helpers import ensure_utc
from app.db.models.workflow import WorkflowModel, WorkflowVersionModel
from app.domain.enums import WorkflowStatus, WorkflowVersionStatus
from app.domain.models.workflow import Workflow, WorkflowVersion


def workflow_version_to_domain(model: WorkflowVersionModel) -> WorkflowVersion:
    """Map WorkflowVersionModel to domain WorkflowVersion entity."""
    return WorkflowVersion(
        id=model.id,
        workflow_id=model.workflow_id,
        version_number=model.version_number,
        specification_version_id=model.specification_version_id,
        definition=dict(model.definition or {}),
        status=WorkflowVersionStatus(model.status),
        change_reason=model.change_reason,
        created_by=model.created_by,
        provider_version_id=model.provider_version_id,
        created_at=ensure_utc(model.created_at),
    )


def workflow_version_to_model(entity: WorkflowVersion) -> WorkflowVersionModel:
    """Map domain WorkflowVersion entity to WorkflowVersionModel."""
    return WorkflowVersionModel(
        id=entity.id,
        workflow_id=entity.workflow_id,
        version_number=entity.version_number,
        specification_version_id=entity.specification_version_id,
        definition=dict(entity.definition or {}),
        status=entity.status.value,
        change_reason=entity.change_reason,
        created_by=entity.created_by,
        provider_version_id=entity.provider_version_id,
        created_at=ensure_utc(entity.created_at),
    )


def workflow_to_domain(model: WorkflowModel) -> Workflow:
    """Map WorkflowModel to domain Workflow aggregate root."""
    versions = [workflow_version_to_domain(v) for v in (model.versions or [])]
    return Workflow(
        id=model.id,
        project_id=model.project_id,
        name=model.name,
        environment=model.environment,
        status=WorkflowStatus(model.status),
        current_version_id=model.current_version_id,
        versions=versions,
        created_at=ensure_utc(model.created_at),
        updated_at=ensure_utc(model.updated_at),
    )


def workflow_to_model(entity: Workflow) -> WorkflowModel:
    """Map domain Workflow aggregate root to WorkflowModel."""
    model = WorkflowModel(
        id=entity.id,
        project_id=entity.project_id,
        name=entity.name,
        environment=entity.environment,
        status=entity.status.value,
        current_version_id=entity.current_version_id,
        created_at=ensure_utc(entity.created_at),
        updated_at=ensure_utc(entity.updated_at),
    )
    model.versions = [workflow_version_to_model(v) for v in entity.versions]
    return model
