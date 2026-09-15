"""Project domain <-> persistence mapper."""

from app.db.mappers.helpers import ensure_utc
from app.db.models.project import ProjectModel
from app.domain.models.project import Project


def project_to_domain(model: ProjectModel) -> Project:
    """Map ProjectModel to domain Project entity."""
    return Project(
        id=model.id,
        name=model.name,
        description=model.description,
        is_active=model.is_active,
        created_at=ensure_utc(model.created_at),
    )


def project_to_model(entity: Project) -> ProjectModel:
    """Map domain Project entity to ProjectModel."""
    return ProjectModel(
        id=entity.id,
        name=entity.name,
        description=entity.description,
        is_active=entity.is_active,
        created_at=ensure_utc(entity.created_at),
    )
