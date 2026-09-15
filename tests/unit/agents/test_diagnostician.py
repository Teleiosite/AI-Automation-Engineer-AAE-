"""Unit tests for DiagnosisEngine and Diagnostician agent component (Phase 14)."""

from uuid import uuid4
import pytest

from app.agents.diagnostician import Diagnostician
from app.domain.enums import (
    ConfidenceLevel,
    FailureCategory,
    FailureSeverity,
    RiskLevel,
    SemanticStatus,
    TechnicalStatus,
)
from app.domain.models.specification import Specification
from app.domain.services.diagnosis_engine import (
    DiagnosisEngine,
    StructuredDiagnosis,
)
from app.domain.services.workflow_test_engine import (
    AssertionType,
    TestAssertion,
    TestCaseResult,
    TestStatus,
)


def test_diagnosis_authentication_error():
    engine = DiagnosisEngine()
    exec_id = uuid4()
    wf_id = uuid4()

    exec_data = {
        "id": exec_id,
        "failed_node": "HTTP Service Request",
        "error_message": "HTTP 401 Unauthorized: Invalid API Token or Credentials expired",
        "execution_path": ["Webhook Trigger", "HTTP Service Request"],
    }

    diag = engine.diagnose_execution(exec_data, workflow_id=wf_id, workflow_version_number=1)

    assert diag.failure_type == FailureCategory.AUTHENTICATION_ERROR
    assert diag.severity == FailureSeverity.HIGH
    assert diag.confidence == ConfidenceLevel.EXPLICIT
    assert diag.confidence_score == 0.95
    assert diag.failure_node == "HTTP Service Request"
    assert diag.last_successful_node == "Webhook Trigger"
    assert "token" in diag.recommended_action.lower() or "credential" in diag.recommended_action.lower()


def test_diagnosis_timeout_error():
    engine = DiagnosisEngine()
    exec_data = {
        "failed_node": "Remote API",
        "error_message": "connect ETIMEDOUT 10.0.0.1:443 after 5000ms",
        "execution_path": ["Trigger", "Prepare Data", "Remote API"],
    }

    diag = engine.diagnose_execution(exec_data)

    assert diag.failure_type == FailureCategory.TIMEOUT
    assert diag.confidence == ConfidenceLevel.EXPLICIT
    assert diag.confidence_score == 0.95
    assert diag.last_successful_node == "Prepare Data"
    assert "retry" in diag.recommended_action.lower()


def test_diagnosis_configuration_syntax_error():
    engine = DiagnosisEngine()
    exec_data = {
        "failed_node": "Format JSON",
        "error_message": "SyntaxError: Unexpected token in parameter expression: {{ $json.missing }",
        "execution_path": ["Webhook", "Format JSON"],
    }

    diag = engine.diagnose_execution(exec_data)

    assert diag.failure_type == FailureCategory.CONFIGURATION_ERROR
    assert diag.confidence == ConfidenceLevel.INFERRED
    assert diag.confidence_score == 0.85
    assert "syntax" in diag.likely_cause.lower() or "expression" in diag.likely_cause.lower()


def test_diagnosis_semantic_logic_error():
    engine = DiagnosisEngine()
    wf_id = uuid4()

    test_res = TestCaseResult(
        scenario_name="Customer Welcome Notification",
        status=TestStatus.FAIL,
        technical_status=TechnicalStatus.SUCCESS,
        semantic_status=SemanticStatus.UNSATISFIED,
        error_message="Semantic assertion failed: output.email_sent was False, expected True",
        assertions=[
            TestAssertion(
                assertion_type=AssertionType.SEMANTIC,
                target="output.email_sent",
                expected=True,
                actual=False,
                passed=False,
                message="Semantic expectation for 'email_sent' violated",
            )
        ],
    )

    diag = engine.diagnose_test_failure(test_res, workflow_id=wf_id, workflow_version_number=2)

    assert diag.failure_type == FailureCategory.LOGIC_ERROR
    assert diag.severity == FailureSeverity.HIGH
    assert diag.confidence == ConfidenceLevel.EXPLICIT
    assert diag.confidence_score == 0.90
    assert "semantic" in diag.likely_cause.lower() or "business" in diag.likely_cause.lower()


def test_diagnosis_execution_path_tracing():
    engine = DiagnosisEngine()
    exec_data = {
        "failed_node": "Postgres Insert",
        "error_message": "duplicate key value violates unique constraint 'users_email_key'",
        "execution_path": ["Start Webhook", "Extract Fields", "Validate Inputs", "Postgres Insert"],
    }

    diag = engine.diagnose_execution(exec_data)

    assert diag.failure_node == "Postgres Insert"
    assert diag.last_successful_node == "Validate Inputs"
    assert len(diag.execution_path) == 4
    assert diag.failure_type == FailureCategory.DATA_ERROR


def test_diagnosis_restrained_confidence_on_unknown_error():
    """Verify that the engine does NOT claim high confidence or certainty when evidence is ambiguous."""
    engine = DiagnosisEngine()
    exec_data = {
        "failed_node": "Mystery Node",
        "error_message": "Unidentified kernel glitch code 0x9999",
        "execution_path": ["Mystery Node"],
    }

    diag = engine.diagnose_execution(exec_data)

    assert diag.failure_type == FailureCategory.UNKNOWN
    assert diag.confidence == ConfidenceLevel.UNKNOWN
    # Must refuse certainty when evidence is insufficient
    assert diag.confidence_score <= 0.50
    assert diag.confidence_score == 0.40


def test_diagnostician_agent_component():
    diagnostician = Diagnostician()

    spec = Specification(project_id=uuid4(), requirement_id=uuid4())
    spec.add_version({
        "business_objective": "Lead sync",
        "success_criteria": ["Lead must sync within 2s without duplication"],
    })

    exec_data = {
        "failed_node": "Sync Service",
        "error_message": "HTTP 403 Forbidden: Missing required write:leads scope",
        "execution_path": ["Trigger", "Sync Service"],
    }

    diag = diagnostician.diagnose_execution(
        execution_data=exec_data,
        specification=spec,
    )

    assert diag.failure_type == FailureCategory.PERMISSION_ERROR
    assert diag.severity == FailureSeverity.HIGH
    assert diag.confidence == ConfidenceLevel.EXPLICIT
    assert "Violates success criteria" in (diag.affected_requirement or "")
    assert diag.risk == RiskLevel.MEDIUM
