"""Unit tests for Execution aggregate and ExecutionResult distinction."""

from datetime import datetime, timedelta, timezone
import pytest
from uuid import uuid4
from app.domain.enums import ExecutionStatus, SemanticStatus, TechnicalStatus, TriggerType
from app.domain.errors import InvariantViolationError
from app.domain.models.execution import Execution, ExecutionResult


def test_technical_vs_semantic_distinction():
    # Technical success (HTTP 200) but semantic failure (wrong business data)
    result = ExecutionResult(
        technical_status=TechnicalStatus.SUCCESS,
        semantic_status=SemanticStatus.UNSATISFIED,
        duration_ms=125.5,
        output_data={"records_sent": 0},
        error_message="Expected 10 records sent, but 0 were matched",
    )
    assert result.technical_status == TechnicalStatus.SUCCESS
    assert result.semantic_status == SemanticStatus.UNSATISFIED
    assert result.duration_ms == 125.5


def test_execution_lifecycle():
    wf_id = uuid4()
    ver_id = uuid4()
    exec_run = Execution(
        workflow_id=wf_id,
        workflow_version_id=ver_id,
        trigger_type=TriggerType.WEBHOOK,
        correlation_id="corr-trace-1",
    )
    assert exec_run.status == ExecutionStatus.QUEUED

    exec_run.start()
    assert exec_run.status == ExecutionStatus.RUNNING

    end_time = exec_run.started_at + timedelta(seconds=2)
    exec_run.complete(
        ExecutionResult(
            technical_status=TechnicalStatus.SUCCESS,
            semantic_status=SemanticStatus.SATISFIED,
            duration_ms=2000.0,
        ),
        finished_at=end_time,
    )
    assert exec_run.status == ExecutionStatus.SUCCESS
    assert exec_run.finished_at == end_time


def test_execution_finished_before_started_fails():
    exec_run = Execution(workflow_id=uuid4(), workflow_version_id=uuid4())
    exec_run.start()
    past_time = exec_run.started_at - timedelta(seconds=5)
    with pytest.raises(InvariantViolationError):
        exec_run.complete(
            ExecutionResult(
                technical_status=TechnicalStatus.SUCCESS,
                semantic_status=SemanticStatus.SATISFIED,
            ),
            finished_at=past_time,
        )
