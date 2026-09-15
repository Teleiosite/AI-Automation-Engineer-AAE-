"""FailureRecord and DiagnosticFinding domain <-> persistence mappers."""

from app.db.mappers.helpers import ensure_utc
from app.db.models.diagnostic import DiagnosticFindingModel, FailureRecordModel
from app.domain.enums import ConfidenceLevel, FailureCategory, FailureSeverity
from app.domain.models.diagnostic import DiagnosticFinding, FailureRecord


def failure_record_to_domain(model: FailureRecordModel) -> FailureRecord:
    """Map FailureRecordModel to domain FailureRecord value object."""
    return FailureRecord(
        id=model.id,
        execution_id=model.execution_id,
        category=FailureCategory(model.category),
        severity=FailureSeverity(model.severity),
        failed_component=model.failed_component,
        message=model.message,
        technical_details=dict(model.technical_details) if model.technical_details is not None else None,
        timestamp=ensure_utc(model.timestamp),
    )


def failure_record_to_model(entity: FailureRecord) -> FailureRecordModel:
    """Map domain FailureRecord to FailureRecordModel."""
    return FailureRecordModel(
        id=entity.id,
        execution_id=entity.execution_id,
        category=entity.category.value,
        severity=entity.severity.value,
        failed_component=entity.failed_component,
        message=entity.message,
        technical_details=dict(entity.technical_details) if entity.technical_details is not None else None,
        timestamp=ensure_utc(entity.timestamp),
    )


def diagnostic_finding_to_domain(model: DiagnosticFindingModel) -> DiagnosticFinding:
    """Map DiagnosticFindingModel to domain DiagnosticFinding value object."""
    return DiagnosticFinding(
        id=model.id,
        failure_id=model.failure_id,
        likely_cause=model.likely_cause,
        confidence=ConfidenceLevel(model.confidence),
        recommended_action=model.recommended_action,
        timestamp=ensure_utc(model.timestamp),
    )


def diagnostic_finding_to_model(entity: DiagnosticFinding) -> DiagnosticFindingModel:
    """Map domain DiagnosticFinding to DiagnosticFindingModel."""
    return DiagnosticFindingModel(
        id=entity.id,
        failure_id=entity.failure_id,
        likely_cause=entity.likely_cause,
        confidence=entity.confidence.value,
        recommended_action=entity.recommended_action,
        timestamp=ensure_utc(entity.timestamp),
    )
