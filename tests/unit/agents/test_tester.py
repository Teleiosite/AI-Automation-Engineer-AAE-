"""Unit tests for WorkflowTestEngine and Tester agent component (Phase 13)."""

from uuid import uuid4
import pytest

from app.agents.tester import Tester
from app.domain.enums import (
    RiskLevel,
    SemanticStatus,
    TechnicalStatus,
    WorkflowVersionStatus,
)
from app.domain.models.specification import Specification
from app.domain.models.workflow import Workflow
from app.domain.services.audit_service import AuditService
from app.domain.services.workflow_test_engine import (
    AssertionType,
    TestRunReport,
    TestScenario,
    TestStatus,
    WorkflowTestEngine,
)


@pytest.fixture
def sample_test_workflow_definition() -> dict:
    return {
        "name": "User Signup Automation",
        "nodes": [
            {
                "id": "node-1",
                "name": "Webhook Trigger",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 1,
                "position": [250, 300],
                "parameters": {"path": "signup", "httpMethod": "POST"},
            },
            {
                "id": "node-2",
                "name": "Save User",
                "type": "n8n-nodes-base.postgres",
                "typeVersion": 1,
                "position": [500, 300],
                "parameters": {"operation": "insert", "table": "users"},
            },
            {
                "id": "node-3",
                "name": "Send Welcome Email",
                "type": "n8n-nodes-base.emailSend",
                "typeVersion": 1,
                "position": [750, 300],
                "parameters": {"toEmail": "={{ $json.email }}"},
            },
        ],
        "connections": {
            "Webhook Trigger": {
                "main": [[{"node": "Save User", "type": "main", "index": 0}]]
            },
            "Save User": {
                "main": [[{"node": "Send Welcome Email", "type": "main", "index": 0}]]
            },
        },
    }


def test_tester_happy_path(sample_test_workflow_definition):
    engine = WorkflowTestEngine()
    wf_id = uuid4()
    ver_id = uuid4()

    scenario = TestScenario(
        name="Valid Signup Flow",
        description="Verify user signup triggers DB save and email delivery",
        inputs={"email": "newuser@example.com", "name": "Jane Doe"},
        expected_outputs={"db_synced": True, "email_sent": True},
        expected_technical_status=TechnicalStatus.SUCCESS,
        expected_semantic_status=SemanticStatus.SATISFIED,
    )

    report = engine.run_tests(
        workflow_id=wf_id,
        workflow_version_id=ver_id,
        definition=sample_test_workflow_definition,
        scenarios=[scenario],
    )

    assert report.all_passed is True
    assert report.total_tests == 1
    assert report.passed_count == 1
    assert report.failed_count == 0
    res = report.results[0]
    assert res.status == TestStatus.PASS
    assert res.technical_status == TechnicalStatus.SUCCESS
    assert res.semantic_status == SemanticStatus.SATISFIED
    assert all(a.passed for a in res.assertions)


def test_tester_technical_success_semantic_failure(sample_test_workflow_definition):
    """Prove that technical execution success (HTTP 200/no errors) does not suffice if semantic expectations fail."""
    engine = WorkflowTestEngine()
    wf_id = uuid4()
    ver_id = uuid4()

    # Scenario expects a field that the workflow does NOT populate
    scenario = TestScenario(
        name="Missing Mandatory Business Attribute",
        description="Expects stripe_charge_id to be populated",
        inputs={"email": "payinguser@example.com"},
        expected_outputs={"db_synced": True, "stripe_charge_id": "ch_12345"},  # Unmet semantic criteria
        expected_technical_status=TechnicalStatus.SUCCESS,
        expected_semantic_status=SemanticStatus.SATISFIED,
    )

    report = engine.run_tests(
        workflow_id=wf_id,
        workflow_version_id=ver_id,
        definition=sample_test_workflow_definition,
        scenarios=[scenario],
    )

    assert report.all_passed is False
    assert report.failed_count == 1
    res = report.results[0]
    assert res.status == TestStatus.FAIL
    # Technical status was SUCCESS
    assert res.technical_status == TechnicalStatus.SUCCESS
    # But Semantic status was UNSATISFIED
    assert res.semantic_status == SemanticStatus.UNSATISFIED
    assert any(not a.passed and a.assertion_type == AssertionType.SEMANTIC for a in res.assertions)


def test_tester_failure_injection(sample_test_workflow_definition):
    """Verify that failure injection accurately tests resilience and negative cases."""
    engine = WorkflowTestEngine()
    wf_id = uuid4()
    ver_id = uuid4()

    scenario = TestScenario(
        name="Database Timeout Test",
        description="Verify failure handling when PostgreSQL is unreachable",
        inputs={"email": "fail@example.com"},
        expected_outputs={},
        expected_technical_status=TechnicalStatus.ERROR,
        expected_semantic_status=SemanticStatus.UNSATISFIED,
        failure_injection={"fail_node": "Save User", "error": "Connection timeout: 5000ms"},
    )

    report = engine.run_tests(
        workflow_id=wf_id,
        workflow_version_id=ver_id,
        definition=sample_test_workflow_definition,
        scenarios=[scenario],
    )

    assert report.all_passed is True
    res = report.results[0]
    assert res.status == TestStatus.PASS
    assert res.technical_status == TechnicalStatus.ERROR
    assert res.semantic_status == SemanticStatus.UNSATISFIED
    assert "timeout" in (res.error_message or "")


def test_tester_generate_scenarios_from_specification():
    engine = WorkflowTestEngine()

    spec = Specification(project_id=uuid4(), requirement_id=uuid4())
    spec.add_version({
        "title": "Lead Router",
        "business_objective": "Route incoming web leads",
        "scope_inclusions": ["webhook", "database", "email"],
        "scope_exclusions": [],
        "trigger": "POST /leads",
        "inputs": ["name", "email", "company"],
        "outputs": ["database record", "email confirmation"],
        "external_systems": ["PostgreSQL", "Email"],
        "risk_level": RiskLevel.LOW.value,
        "success_criteria": ["Lead stored in DB", "Email sent to sales"],
    })

    scenarios = engine.generate_scenarios_from_specification(spec)
    assert len(scenarios) >= 2
    assert any("Happy Path" in s.name for s in scenarios)
    assert any("Failure" in s.name for s in scenarios)


def test_tester_agent_lifecycle_promotion(sample_test_workflow_definition):
    tester_agent = Tester()

    wf = Workflow(project_id=uuid4(), name="Agent Test Workflow")
    version = wf.add_version(
        specification_version_id=uuid4(),
        definition=sample_test_workflow_definition,
        change_reason="Built by Builder agent",
    )

    # Move version to VALIDATED status
    version.validate()
    assert version.status == WorkflowVersionStatus.VALIDATED

    # Test with passing scenario
    passing_scenario = TestScenario(
        name="Pass Case",
        description="Verify normal execution",
        inputs={"email": "test@test.com"},
        expected_outputs={"db_synced": True},
        expected_technical_status=TechnicalStatus.SUCCESS,
        expected_semantic_status=SemanticStatus.SATISFIED,
    )

    rep = tester_agent.test_workflow(wf, scenarios=[passing_scenario])
    assert rep.all_passed is True
    # Verify version status promoted to TESTED
    assert version.status == WorkflowVersionStatus.TESTED


def test_tester_audit_logging(sample_test_workflow_definition):
    audit_service = AuditService()
    engine = WorkflowTestEngine(audit_service=audit_service)

    wf_id = uuid4()
    ver_id = uuid4()

    scenario = TestScenario(
        name="Audit Test",
        description="Verify audit emission",
        inputs={"email": "audit@test.com"},
        expected_outputs={"db_synced": True},
        expected_technical_status=TechnicalStatus.SUCCESS,
        expected_semantic_status=SemanticStatus.SATISFIED,
    )

    engine.run_tests(
        workflow_id=wf_id,
        workflow_version_id=ver_id,
        definition=sample_test_workflow_definition,
        scenarios=[scenario],
        correlation_id="corr-test-123",
    )

    events = audit_service.get_buffered_events()
    assert len(events) >= 1
    assert any(e.event_type == "workflow.tested" for e in events)
    test_event = next(e for e in events if e.event_type == "workflow.tested")
    assert test_event.correlation_id == "corr-test-123"
    assert test_event.metadata["after_hash"] is not None
