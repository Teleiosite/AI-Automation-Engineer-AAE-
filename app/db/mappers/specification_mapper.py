"""Specification and SpecificationVersion domain <-> persistence mappers."""

from app.db.mappers.helpers import ensure_utc
from app.db.models.specification import SpecificationModel, SpecificationVersionModel
from app.domain.enums import SpecificationStatus
from app.domain.models.specification import Specification, SpecificationVersion


def specification_version_to_domain(model: SpecificationVersionModel) -> SpecificationVersion:
    """Map SpecificationVersionModel to domain SpecificationVersion entity."""
    return SpecificationVersion(
        id=model.id,
        specification_id=model.specification_id,
        version_number=model.version_number,
        structured_content=dict(model.structured_content or {}),
        is_approved=model.is_approved,
        created_at=ensure_utc(model.created_at),
    )


def specification_version_to_model(entity: SpecificationVersion) -> SpecificationVersionModel:
    """Map domain SpecificationVersion entity to SpecificationVersionModel."""
    return SpecificationVersionModel(
        id=entity.id,
        specification_id=entity.specification_id,
        version_number=entity.version_number,
        structured_content=dict(entity.structured_content or {}),
        is_approved=entity.is_approved,
        created_at=ensure_utc(entity.created_at),
    )


def specification_to_domain(model: SpecificationModel) -> Specification:
    """Map SpecificationModel to domain Specification aggregate root."""
    versions = [specification_version_to_domain(v) for v in (model.versions or [])]
    return Specification(
        id=model.id,
        project_id=model.project_id,
        requirement_id=model.requirement_id,
        status=SpecificationStatus(model.status),
        current_version_number=model.current_version_number,
        versions=versions,
        created_at=ensure_utc(model.created_at),
        updated_at=ensure_utc(model.updated_at),
    )


def specification_to_model(entity: Specification) -> SpecificationModel:
    """Map domain Specification aggregate root to SpecificationModel."""
    model = SpecificationModel(
        id=entity.id,
        project_id=entity.project_id,
        requirement_id=entity.requirement_id,
        status=entity.status.value,
        current_version_number=entity.current_version_number,
        created_at=ensure_utc(entity.created_at),
        updated_at=ensure_utc(entity.updated_at),
    )
    model.versions = [specification_version_to_model(v) for v in entity.versions]
    return model
