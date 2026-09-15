"""Project repository adapter."""

from typing import List, Optional
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db.mappers.project_mapper import project_to_domain, project_to_model
from app.db.models.project import ProjectModel
from app.domain.models.project import Project


class ProjectRepository:
    """Repository managing Project aggregate persistence."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, project_id: UUID) -> Optional[Project]:
        """Fetch project by UUID."""
        stmt = select(ProjectModel).where(ProjectModel.id == project_id)
        model = self._session.execute(stmt).scalar_one_or_none()
        return project_to_domain(model) if model else None

    def get_by_name(self, name: str) -> Optional[Project]:
        """Fetch project by unique name."""
        stmt = select(ProjectModel).where(ProjectModel.name == name)
        model = self._session.execute(stmt).scalar_one_or_none()
        return project_to_domain(model) if model else None

    def save(self, project: Project) -> Project:
        """Persist or update Project entity."""
        stmt = select(ProjectModel).where(ProjectModel.id == project.id)
        model = self._session.execute(stmt).scalar_one_or_none()
        if model:
            model.name = project.name
            model.description = project.description
            model.is_active = project.is_active
        else:
            model = project_to_model(project)
            self._session.add(model)
        self._session.flush()
        return project_to_domain(model)

    def list(self) -> List[Project]:
        """List all projects."""
        stmt = select(ProjectModel).order_by(ProjectModel.name)
        models = self._session.execute(stmt).scalars().all()
        return [project_to_domain(m) for m in models]
