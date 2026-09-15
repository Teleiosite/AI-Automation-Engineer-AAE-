"""Execution and ExecutionResult domain <-> persistence mappers."""

from typing import Optional
from app.db.mappers.helpers import ensure_utc
from app.db.models.execution import ExecutionModel
from app.domain.enums import ExecutionStatus, SemanticStatus, TechnicalStatus, TriggerType
from app.domain.models.execution import Execution, ExecutionResult


def execution_result_to_domain(model: ExecutionModel) -> Optional[ExecutionResult]:
    """Extract embedded ExecutionResult value object from ExecutionModel."""
    if not model.result_technical_status or not model.result_semantic_status:
        return None
    return ExecutionResult(
        technical_status=TechnicalStatus(model.result_technical_status),
        semantic_status=SemanticStatus(model.result_semantic_status),
        duration_ms=float(model.result_duration_ms or 0.0),
        output_data=dict(model.result_output_data) if model.result_output_data is not None else None,
        error_message=model.result_error_message,
        error_details=dict(model.result_error_details) if model.result_error_details is not None else None,
    )


def execution_to_domain(model: ExecutionModel) -> Execution:
    """Map ExecutionModel to domain Execution aggregate."""
    result = execution_result_to_domain(model)
    return Execution(
        id=model.id,
        workflow_id=model.workflow_id,
        workflow_version_id=model.workflow_version_id,
        status=ExecutionStatus(model.status),
        trigger_type=TriggerType(model.trigger_type),
        started_at=ensure_utc(model.started_at),
        finished_at=ensure_utc(model.finished_at),
        result=result,
        correlation_id=model.correlation_id,
    )


def execution_to_model(entity: Execution) -> ExecutionModel:
    """Map domain Execution aggregate to ExecutionModel."""
    model = ExecutionModel(
        id=entity.id,
        workflow_id=entity.workflow_id,
        workflow_version_id=entity.workflow_version_id,
        status=entity.status.value,
        trigger_type=entity.trigger_type.value,
        started_at=ensure_utc(entity.started_at),
        finished_at=ensure_utc(entity.finished_at),
        correlation_id=entity.correlation_id,
    )
    if entity.result is not None:
        model.result_technical_status = entity.result.technical_status.value
        model.result_semantic_status = entity.result.semantic_status.value
        model.result_duration_ms = entity.result.duration_ms
        model.result_output_data = entity.result.output_data
        model.result_error_message = entity.result.error_message
        model.result_error_details = entity.result.error_details
    return model
