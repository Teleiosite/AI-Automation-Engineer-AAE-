"""Unit tests for RegressionEngine and RegressionRunner agent component (Phase 16)."""

from uuid import uuid4
import pytest

from app.agents.regression_runner import RegressionRunner
from app.domain.enums import (
    SemanticStatus,
    TechnicalStatus,
    WorkflowVersionStatus,
)
from app.domain.models.workflow import Workflow
from app.domain.services.audit_service import AuditService
from app.domain.services.regression_engine import (
    RegressionEngine,
    RegressionResult,
    RegressionSuite,
)
from app.domain.services.workflow_test_engine import (
    TestScenario,
    WorkflowTestEngine,
)


@pytest.fixture
def regression_workflow() -> Workflow:
    wf = Workflow(project_id=uuid4(), name="Order Fulfillment Service")
    wf.add_version(
        specification_version_id=uuid4(),
        definition={
            "name": "Order Fulfillment Service",
            "nodes": [
                {
                    "id": "node-1",
                    "name": "Order Webhook",
                    "type": "n8n-nodes-base.webhook",
                    "typeVersion": 1,
                    "parameters": {"path": "orders"},
                },
                {
                    "id": "node-2",
                    "name": "Process Payment",
                    "type": "n8n-nodes-base.httpRequest",
                    "typeVersion": 1,
                    "parameters": {"url": "https://payments.internal/charge"},
                },
                {
                    "id": "node-3",
                    "name": "Store Order",
                    "type": "n8n-nodes-base.postgres",
                    "typeVersion": 1,
                    "parameters": {"operation": "insert", "table": "orders"},
                },
            ],
            "connections": {
                "Order Webhook": {"main": [[{"node": "Process Payment", "type": "main", "index": 0}]]},
                "Process Payment": {"main": [[{"node": "Store Order", "type": "main", "index": 0}]]},
            },
        },
        change_reason="Initial build",
    )
    return wf


def test_regression_test_selection(regression_workflow):
    engine = RegressionEngine()
    wf_id = regression_workflow.id

    crit_scenario = TestScenario(
        name="Critical Health Ping",
        description="Verify core webhook endpoint responds",
        inputs={},
        expected_outputs={},
    )
    affected_scenario = TestScenario(
        name="Payment Payload Schema",
        description="Verify payment gateway accepts charge format",
        inputs={"amount": 100},
        expected_outputs={"http_status": 200},
    )
    unaffected_scenario = TestScenario(
        name="Database Index Verification",
        description="Verify order database insert index",
        inputs={"id": "ord-1"},
        expected_outputs={"db_synced": True},
    )

    # Register scenarios
    engine.register_scenario(wf_id, crit_scenario, is_critical=True)
    engine.register_scenario(wf_id, affected_scenario, is_critical=False, covered_nodes=["Process Payment"])
    engine.register_scenario(wf_id, unaffected_scenario, is_critical=False, covered_nodes=["Store Order"])

    failing_scenario = TestScenario(
        name="Payment Gateway Timeout",
        description="Failed on payment network timeout",
        inputs={"amount": 50},
        expected_outputs={"http_status": 200},
    )

    selected = engine.select_tests_for_repair(
        workflow_id=wf_id,
        failing_scenario=failing_scenario,
        touched_nodes=["Process Payment"],
    )

    selected_names = {s.name for s in selected}
    assert failing_scenario.name in selected_names
    assert crit_scenario.name in selected_names
    assert affected_scenario.name in selected_names
    # Unaffected scenario covering only "Store Order" should NOT be selected
    assert unaffected_scenario.name not in selected_names


def test_regression_happy_path_repair_passes(regression_workflow):
    engine = RegressionEngine()
    wf_id = regression_workflow.id

    # Baseline critical test
    crit_test = TestScenario(
        name="Baseline Webhook Intake",
        description="Verifies order webhook is reachable",
        inputs={"order_id": "123"},
        expected_outputs={},
    )
    engine.register_scenario(wf_id, crit_test, is_critical=True)

    # Repaired scenario (now working)
    repaired_scenario = TestScenario(
        name="Repaired Payment Processing",
        description="Verifies payment now succeeds after retry policy added",
        inputs={"order_id": "123"},
        expected_outputs={"http_status": 200, "db_synced": True},
        expected_technical_status=TechnicalStatus.SUCCESS,
        expected_semantic_status=SemanticStatus.SATISFIED,
    )

    result = engine.run_regression(
        workflow=regression_workflow,
        version_number=1,
        failing_scenario=repaired_scenario,
        touched_nodes=["Process Payment"],
    )

    assert result.all_passed is True
    assert result.repaired_test_passed is True
    assert result.critical_tests_passed is True
    assert result.drift_detected is False
    assert result.total_scenarios_evaluated >= 2


def test_regression_detects_introduced_regression(regression_workflow):
    """Verify that if a repair breaks a critical baseline invariant, regression fails."""
    engine = RegressionEngine()
    wf_id = regression_workflow.id

    # Baseline test expects db_synced to be True
    crit_test = TestScenario(
        name="Critical DB Persistence",
        description="Verifies database records are created",
        inputs={"order_id": "123"},
        # Expect an impossible field to simulate regression failure in baseline
        expected_outputs={"db_synced": True, "broken_field_must_exist": "impossible"},
        expected_technical_status=TechnicalStatus.SUCCESS,
        expected_semantic_status=SemanticStatus.SATISFIED,
    )
    engine.register_scenario(wf_id, crit_test, is_critical=True)

    repaired_scenario = TestScenario(
        name="Repaired Scenario",
        description="Fixes the bug",
        inputs={},
        expected_outputs={},
        expected_technical_status=TechnicalStatus.SUCCESS,
        expected_semantic_status=SemanticStatus.SATISFIED,
    )

    result = engine.run_regression(
        workflow=regression_workflow,
        version_number=1,
        failing_scenario=repaired_scenario,
    )

    assert result.all_passed is False
    assert result.repaired_test_passed is True
    assert result.critical_tests_passed is False
    assert result.drift_detected is True


def test_regression_runner_agent_integration(regression_workflow):
    runner = RegressionRunner()
    wf_id = regression_workflow.id

    crit_test = TestScenario(
        name="Order Intake",
        description="Verify intake",
        inputs={},
        expected_outputs={},
    )
    runner.register_baseline_scenario(wf_id, crit_test, is_critical=True)

    failing_test = TestScenario(
        name="Repaired Payment",
        description="Repaired payment",
        inputs={},
        expected_outputs={"http_status": 200},
    )

    res = runner.verify_repair(
        workflow=regression_workflow,
        version_number=1,
        failing_scenario=failing_test,
    )

    assert res.all_passed is True
    assert res.workflow_id == wf_id


def test_regression_audit_event_logging(regression_workflow):
    audit_service = AuditService()
    engine = RegressionEngine(audit_service=audit_service)

    failing_scenario = TestScenario(
        name="Audit Test Scenario",
        description="Audit test",
        inputs={},
        expected_outputs={},
    )

    engine.run_regression(
        workflow=regression_workflow,
        version_number=1,
        failing_scenario=failing_scenario,
        correlation_id="corr-reg-1",
    )

    events = audit_service.get_buffered_events()
    assert any(e.event_type == "workflow.regression_tested" for e in events)
    reg_event = next(e for e in events if e.event_type == "workflow.regression_tested")
    assert reg_event.correlation_id == "corr-reg-1"
    assert reg_event.metadata["after_hash"] is not None
