"""Requirement and RequirementItem domain <-> persistence mappers."""

from app.db.mappers.helpers import ensure_utc
from app.db.models.requirement import RequirementItemModel, RequirementModel
from app.domain.enums import ConfidenceLevel, RequirementType, RiskLevel
from app.domain.models.requirement import Requirement, RequirementItem


def requirement_item_to_domain(model: RequirementItemModel) -> RequirementItem:
    """Map RequirementItemModel to domain RequirementItem value object."""
    return RequirementItem(
        id=model.id,
        type=RequirementType(model.type),
        description=model.description,
        confidence=ConfidenceLevel(model.confidence),
        risk=RiskLevel(model.risk),
        notes=model.notes,
    )


def requirement_item_to_model(entity: RequirementItem, requirement_id) -> RequirementItemModel:
    """Map domain RequirementItem to RequirementItemModel."""
    return RequirementItemModel(
        id=entity.id,
        requirement_id=requirement_id,
        type=entity.type.value,
        description=entity.description,
        confidence=entity.confidence.value,
        risk=entity.risk.value,
        notes=entity.notes,
    )


def requirement_to_domain(model: RequirementModel) -> Requirement:
    """Map RequirementModel to domain Requirement aggregate."""
    items = [requirement_item_to_domain(item) for item in (model.items or [])]
    return Requirement(
        id=model.id,
        project_id=model.project_id,
        original_request=model.original_request,
        created_by=model.created_by,
        version=model.version,
        items=items,
        assumptions=list(model.assumptions or []),
        ambiguities=list(model.ambiguities or []),
        conflicts=list(model.conflicts or []),
        created_at=ensure_utc(model.created_at),
    )


def requirement_to_model(entity: Requirement) -> RequirementModel:
    """Map domain Requirement aggregate to RequirementModel."""
    model = RequirementModel(
        id=entity.id,
        project_id=entity.project_id,
        original_request=entity.original_request,
        created_by=entity.created_by,
        version=entity.version,
        assumptions=list(entity.assumptions or []),
        ambiguities=list(entity.ambiguities or []),
        conflicts=list(entity.conflicts or []),
        created_at=ensure_utc(entity.created_at),
    )
    model.items = [requirement_item_to_model(item, entity.id) for item in entity.items]
    return model
