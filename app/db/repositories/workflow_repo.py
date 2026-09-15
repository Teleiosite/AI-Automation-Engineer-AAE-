"""Workflow repository adapter with concurrency-safe versioning."""

from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload
from app.db.mappers.workflow_mapper import (
    workflow_to_domain,
    workflow_to_model,
    workflow_version_to_domain,
    workflow_version_to_model,
)
from app.db.models.workflow import WorkflowModel, WorkflowVersionModel
from app.domain.enums import WorkflowVersionStatus
from app.domain.errors import ImmutableArtifactError, InvariantViolationError
from app.domain.models.workflow import Workflow, WorkflowVersion


class WorkflowRepository:
    """Repository managing Workflow aggregate and concurrency-safe version allocation."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, workflow_id: UUID) -> Optional[Workflow]:
        """Fetch workflow aggregate with all its versions."""
        stmt = (
            select(WorkflowModel)
            .options(selectinload(WorkflowModel.versions))
            .where(WorkflowModel.id == workflow_id)
        )
        model = self._session.execute(stmt).scalar_one_or_none()
        return workflow_to_domain(model) if model else None

    def get_version(self, workflow_id: UUID, version_number: int) -> Optional[WorkflowVersion]:
        """Fetch a specific version by workflow ID and version number."""
        stmt = (
            select(WorkflowVersionModel)
            .where(
                WorkflowVersionModel.workflow_id == workflow_id,
                WorkflowVersionModel.version_number == version_number,
            )
        )
        model = self._session.execute(stmt).scalar_one_or_none()
        return workflow_version_to_domain(model) if model else None

    def get_version_by_id(self, version_id: UUID) -> Optional[WorkflowVersion]:
        """Fetch version by its unique UUID."""
        stmt = select(WorkflowVersionModel).where(WorkflowVersionModel.id == version_id)
        model = self._session.execute(stmt).scalar_one_or_none()
        return workflow_version_to_domain(model) if model else None

    def save(self, workflow: Workflow) -> Workflow:
        """Persist or update Workflow aggregate."""
        stmt = (
            select(WorkflowModel)
            .options(selectinload(WorkflowModel.versions))
            .where(WorkflowModel.id == workflow.id)
        )
        model = self._session.execute(stmt).scalar_one_or_none()

        if model:
            model.name = workflow.name
            model.environment = workflow.environment
            model.status = workflow.status.value
            model.current_version_id = workflow.current_version_id

            # Check immutability on versions
            existing_vers = {v.version_number: v for v in model.versions}
            for domain_ver in workflow.versions:
                if domain_ver.version_number in existing_vers:
                    m_ver = existing_vers[domain_ver.version_number]
                    is_locked = m_ver.status in (
                        WorkflowVersionStatus.APPROVED.value,
                        WorkflowVersionStatus.DEPLOYED.value,
                        WorkflowVersionStatus.SUPERSEDED.value,
                    )
                    if is_locked and m_ver.definition != domain_ver.definition:
                        raise ImmutableArtifactError(
                            f"Workflow version {m_ver.version_number} is in state '{m_ver.status}' and cannot be modified"
                        )
                    m_ver.status = domain_ver.status.value
                    m_ver.definition = domain_ver.definition
                    m_ver.change_reason = domain_ver.change_reason
                    m_ver.provider_version_id = domain_ver.provider_version_id
                else:
                    new_m_ver = workflow_version_to_model(domain_ver)
                    model.versions.append(new_m_ver)
        else:
            model = workflow_to_model(workflow)
            self._session.add(model)

        self._session.flush()
        return workflow_to_domain(model)

    def create_version_atomic(
        self,
        workflow_id: UUID,
        specification_version_id: UUID,
        definition: Dict[str, Any],
        change_reason: str = "New revision",
        created_by: str = "agent",
    ) -> WorkflowVersion:
        """
        Concurrency-safe version allocation using row-level locking on the parent aggregate.
        Guarantees no duplicate committed version numbers for the same workflow.
        """
        # 1. Lock the parent workflow row
        stmt = (
            select(WorkflowModel)
            .where(WorkflowModel.id == workflow_id)
            .with_for_update()
        )
        wf_model = self._session.execute(stmt).scalar_one_or_none()
        if not wf_model:
            raise InvariantViolationError(f"Workflow '{workflow_id}' does not exist")

        # 2. Determine next sequential version number under parent lock
        max_ver_stmt = select(func.max(WorkflowVersionModel.version_number)).where(
            WorkflowVersionModel.workflow_id == workflow_id
        )
        max_ver = self._session.execute(max_ver_stmt).scalar() or 0
        next_ver = max_ver + 1

        # 3. Insert new version
        ver_model = WorkflowVersionModel(
            id=uuid4(),
            workflow_id=workflow_id,
            version_number=next_ver,
            specification_version_id=specification_version_id,
            definition=definition,
            change_reason=change_reason,
            created_by=created_by,
        )
        self._session.add(ver_model)

        # 4. Update workflow's current version ID
        wf_model.current_version_id = ver_model.id
        self._session.flush()

        return workflow_version_to_domain(ver_model)

    def list_for_project(self, project_id: UUID) -> List[Workflow]:
        """List workflows belonging to a project."""
        stmt = (
            select(WorkflowModel)
            .options(selectinload(WorkflowModel.versions))
            .where(WorkflowModel.project_id == project_id)
            .order_by(WorkflowModel.name)
        )
        models = self._session.execute(stmt).scalars().all()
        return [workflow_to_domain(m) for m in models]
