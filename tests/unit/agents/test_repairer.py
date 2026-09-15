"""Unit tests for RepairEngine and Repairer agent component (Phase 15)."""

from uuid import uuid4
import pytest

from app.agents.repairer import Repairer
from app.domain.enums import (
    ConfidenceLevel,
    FailureCategory,
    FailureSeverity,
    RiskLevel,
    WorkflowVersionStatus,
)
from app.domain.models.workflow import Workflow
from app.domain.services.audit_service import AuditService
from app.domain.services.diagnosis_engine import StructuredDiagnosis
from app.domain.services.repair_engine import (
    PatchType,
    RepairEngine,
    RepairPatch,
    RepairProposal,
)
from app.domain.services.workflow_validator import WorkflowValidator


@pytest.fixture
def sample_broken_workflow() -> Workflow:
    wf = Workflow(project_id=uuid4(), name="Lead Ingestion Pipeline")
    wf.add_version(
        specification_version_id=uuid4(),
        definition={
            "name": "Lead Ingestion Pipeline",
            "nodes": [
                {
                    "id": "node-1",
                    "name": "Webhook Trigger",
                    "type": "n8n-nodes-base.webhook",
                    "typeVersion": 1,
                    "parameters": {"path": "leads"},
                },
                {
                    "id": "node-2",
                    "name": "HTTP Enrichment",
                    "type": "n8n-nodes-base.httpRequest",
                    "typeVersion": 1,
                    "parameters": {
                        "url": "https://enrichment.service/api",
                        "malformed_field": "={{ $json.company_name }",  # Unclosed brace
                    },
                },
            ],
            "connections": {
                "Webhook Trigger": {
                    "main": [[{"node": "HTTP Enrichment", "type": "main", "index": 0}]]
                }
            },
        },
        change_reason="Initial build",
    )
    return wf


def test_repair_propose_timeout_retry_policy(sample_broken_workflow):
    engine = RepairEngine()
    diag = StructuredDiagnosis(
        execution_id=uuid4(),
        workflow_id=sample_broken_workflow.id,
        workflow_version_number=1,
        failure_node="HTTP Enrichment",
        failure_type=FailureCategory.TIMEOUT,
        severity=FailureSeverity.MEDIUM,
        error_message="Connection timed out after 5000ms",
        execution_path=["Webhook Trigger", "HTTP Enrichment"],
        last_successful_node="Webhook Trigger",
        likely_cause="Network timeout on remote enrichment service",
        confidence=ConfidenceLevel.EXPLICIT,
        confidence_score=0.95,
        recommended_action="Enable retryOnFail policy",
    )

    cur_def = sample_broken_workflow.get_current_version().definition
    proposal = engine.propose_repair(diag, cur_def)

    assert len(proposal.patches) >= 2
    assert any(p.patch_type == PatchType.RETRY_POLICY and p.field_path == "retryOnFail" and p.new_value is True for p in proposal.patches)
    assert any(p.patch_type == PatchType.RETRY_POLICY and p.field_path == "maxTries" and p.new_value == 3 for p in proposal.patches)


def test_repair_propose_unclosed_expression_fix(sample_broken_workflow):
    engine = RepairEngine()
    diag = StructuredDiagnosis(
        execution_id=uuid4(),
        workflow_id=sample_broken_workflow.id,
        workflow_version_number=1,
        failure_node="HTTP Enrichment",
        failure_type=FailureCategory.CONFIGURATION_ERROR,
        severity=FailureSeverity.HIGH,
        error_message="SyntaxError: Unexpected token in parameter expression: {{ $json.company_name }",
        execution_path=["Webhook Trigger", "HTTP Enrichment"],
        last_successful_node="Webhook Trigger",
        likely_cause="Unclosed parameter expression",
        confidence=ConfidenceLevel.INFERRED,
        confidence_score=0.85,
        recommended_action="Close parameter expression braces",
    )

    cur_def = sample_broken_workflow.get_current_version().definition
    proposal = engine.propose_repair(diag, cur_def)

    assert len(proposal.patches) == 1
    patch = proposal.patches[0]
    assert patch.patch_type == PatchType.EXPRESSION_FIX
    assert patch.field_path == "parameters.malformed_field"
    # Verify closing brace was added
    assert patch.new_value == "={{ $json.company_name }}"


def test_repair_applies_version_without_mutating_history(sample_broken_workflow):
    engine = RepairEngine()
    v1 = sample_broken_workflow.get_current_version()
    v1_raw_param = v1.definition["nodes"][1]["parameters"]["malformed_field"]

    proposal = RepairProposal(
        diagnosis_id=uuid4(),
        workflow_id=sample_broken_workflow.id,
        target_version_number=1,
        patches=[
            RepairPatch(
                target_node="HTTP Enrichment",
                patch_type=PatchType.EXPRESSION_FIX,
                field_path="parameters.malformed_field",
                new_value="={{ $json.company_name }}",
                rationale="Fix unclosed brace",
            )
        ],
        rationale="Expression brace fix",
    )

    new_ver, attempt = engine.apply_repair(sample_broken_workflow, proposal)

    assert len(sample_broken_workflow.versions) == 2
    assert new_ver.version_number == 2
    assert attempt.status == "APPLIED"
    assert attempt.target_version_number == 2

    # Verify v2 has the patch
    assert new_ver.definition["nodes"][1]["parameters"]["malformed_field"] == "={{ $json.company_name }}"

    # Verify v1 remains strictly intact (immutability preserved)
    assert v1.definition["nodes"][1]["parameters"]["malformed_field"] == v1_raw_param
    assert sample_broken_workflow.versions[0].version_number == 1


def test_repair_agent_with_immediate_validation(sample_broken_workflow):
    repairer = Repairer()
    v1_def = sample_broken_workflow.get_current_version().definition

    # Pre-validation fails on v1 due to unclosed expression
    pre_val = WorkflowValidator().validate(v1_def)
    assert any(i.rule_id == "EXP-001" for i in pre_val.issues)

    diag = StructuredDiagnosis(
        execution_id=uuid4(),
        workflow_id=sample_broken_workflow.id,
        workflow_version_number=1,
        failure_node="HTTP Enrichment",
        failure_type=FailureCategory.CONFIGURATION_ERROR,
        severity=FailureSeverity.HIGH,
        error_message="Malformed expression with unbalanced braces",
        execution_path=["Webhook Trigger", "HTTP Enrichment"],
        last_successful_node="Webhook Trigger",
        likely_cause="Unclosed brace",
        confidence=ConfidenceLevel.INFERRED,
        confidence_score=0.85,
        recommended_action="Balance braces",
    )

    proposal = repairer.propose(diag, sample_broken_workflow)
    new_ver, attempt, val_report = repairer.repair(sample_broken_workflow, proposal)

    assert val_report.is_valid is True
    assert new_ver.status == WorkflowVersionStatus.VALIDATED
    assert attempt.status == "APPLIED"


def test_repair_rollback_functionality(sample_broken_workflow):
    engine = RepairEngine()

    # Apply a change creating v2
    v1_nodes_count = len(sample_broken_workflow.get_current_version().definition["nodes"])
    proposal = RepairProposal(
        diagnosis_id=uuid4(),
        workflow_id=sample_broken_workflow.id,
        target_version_number=1,
        patches=[
            RepairPatch(
                target_node="HTTP Enrichment",
                patch_type=PatchType.PARAMETER_UPDATE,
                field_path="parameters.bad_field",
                new_value="broken",
                rationale="Bad patch",
            )
        ],
        rationale="Testing rollback",
    )
    engine.apply_repair(sample_broken_workflow, proposal)
    assert len(sample_broken_workflow.versions) == 2

    # Now rollback to v1
    v3 = engine.rollback(sample_broken_workflow, target_version_number=1, reason="v2 was defective")

    assert len(sample_broken_workflow.versions) == 3
    assert v3.version_number == 3
    assert "Rollback to version 1" in v3.change_reason
    assert "bad_field" not in v3.definition["nodes"][1]["parameters"]


def test_repair_audit_event_logging(sample_broken_workflow):
    audit_service = AuditService()
    engine = RepairEngine(audit_service=audit_service)

    proposal = RepairProposal(
        diagnosis_id=uuid4(),
        workflow_id=sample_broken_workflow.id,
        target_version_number=1,
        patches=[
            RepairPatch(
                target_node="HTTP Enrichment",
                patch_type=PatchType.RETRY_POLICY,
                field_path="retryOnFail",
                new_value=True,
                rationale="Add retry",
            )
        ],
        rationale="Audit test repair",
    )

    engine.apply_repair(sample_broken_workflow, proposal, correlation_id="corr-repair-1")

    events = audit_service.get_buffered_events()
    assert any(e.event_type == "workflow.repaired" for e in events)
    repair_event = next(e for e in events if e.event_type == "workflow.repaired")
    assert repair_event.correlation_id == "corr-repair-1"
    assert repair_event.metadata["after_hash"] is not None
