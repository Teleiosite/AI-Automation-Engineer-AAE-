"""Unit tests for AuditService, state hashing, and governance traceability (Phase 6)."""

from uuid import uuid4
import pytest

from app.domain.enums import ApprovalDecision, ApprovalStatus
from app.domain.models.approval import Approval
from app.domain.models.audit import AuditEvent
from app.domain.policy.models import Environment, PolicyAction, PolicyDecision, PolicyDecisionType, RiskLevel
from app.domain.services.audit_service import AuditService, compute_state_hash


@pytest.fixture
def sink_events():
    events = []
    def sink(event):
        events.append(event)
    return events, sink


@pytest.fixture
def audit_service(sink_events):
    events, sink = sink_events
    return AuditService(sink=sink)


def test_compute_state_hash_is_deterministic():
    data1 = {"b": 2, "a": 1, "nodes": ["nodeA", "nodeB"]}
    data2 = {"a": 1, "b": 2, "nodes": ["nodeA", "nodeB"]}
    hash1 = compute_state_hash(data1)
    hash2 = compute_state_hash(data2)
    assert hash1 == hash2
    assert len(hash1) == 64  # SHA-256


# Acceptance Criterion 1: Every material workflow mutation produces an audit event with hashes
def test_record_workflow_mutation(audit_service, sink_events):
    events, _ = sink_events
    wf_id = str(uuid4())
    before_state = {"version": 1, "nodes": [{"name": "A"}]}
    after_state = {"version": 2, "nodes": [{"name": "A"}, {"name": "B"}]}

    event = audit_service.record_workflow_mutation(
        mutation_type="updated",
        workflow_id=wf_id,
        actor="engineer_bob",
        version_number=2,
        before_state=before_state,
        after_state=after_state,
        change_reason="Added node B for Slack notification",
        correlation_id="cid-wf-update-123",
    )

    assert isinstance(event, AuditEvent)
    assert event.event_type == "workflow.updated"
    assert event.target_type == "workflow"
    assert event.target_id == wf_id
    assert event.correlation_id == "cid-wf-update-123"
    assert event.metadata["version_number"] == 2
    assert event.metadata["before_hash"] == compute_state_hash(before_state)
    assert event.metadata["after_hash"] == compute_state_hash(after_state)
    assert event.metadata["before_hash"] != event.metadata["after_hash"]
    assert len(events) == 1
    assert events[0] == event


# Acceptance Criterion 2: Security decision evaluation produces an audit event
def test_record_security_decision(audit_service, sink_events):
    decision = PolicyDecision(
        decision=PolicyDecisionType.REQUIRE_APPROVAL,
        action=PolicyAction.DEPLOY,
        risk_level=RiskLevel.HIGH,
        reason="Production deployment requires approval gate",
        required_approval_type="PRODUCTION_DEPLOYMENT_GATE",
    )
    wf_id = str(uuid4())

    event = audit_service.record_security_decision(
        actor="agent_codex",
        decision=decision,
        target_type="workflow",
        target_id=wf_id,
        correlation_id="cid-sec-dec-456",
    )

    assert event.event_type == "security.decision"
    assert event.outcome == "REQUIRE_APPROVAL"
    assert event.metadata["action"] == "DEPLOY"
    assert event.metadata["risk_level"] == "HIGH"
    assert event.correlation_id == "cid-sec-dec-456"


# Acceptance Criterion 3: Approval lifecycle produces audit events
def test_record_approval_lifecycle(audit_service):
    target_id = uuid4()
    approval = Approval(
        target_type="workflow",
        target_id=target_id,
        target_version=1,
        actor="admin_alice",
        action="deploy",
        environment="production",
        status=ApprovalStatus.ACTIVE,
        decision=ApprovalDecision.APPROVED,
    )

    # 1. Created
    ev_created = audit_service.record_approval_lifecycle("created", approval, actor="agent", correlation_id="cid-appr-1")
    assert ev_created.event_type == "approval.created"
    assert ev_created.target_type == "approval"
    assert ev_created.target_id == str(approval.id)
    assert ev_created.outcome == "ACTIVE"

    # 2. Consumed
    action_id = uuid4()
    approval.consume(action_id)
    ev_consumed = audit_service.record_approval_lifecycle("consumed", approval, actor="deployment_service", correlation_id="cid-appr-2")
    assert ev_consumed.event_type == "approval.consumed"
    assert ev_consumed.outcome == "CONSUMED"
    assert ev_consumed.metadata["consumed_by_action_id"] == str(action_id)


# Acceptance Criterion 4: Deployment events record workflow, version, and approval ID
def test_record_deployment_event(audit_service):
    dep_id = str(uuid4())
    wf_id = str(uuid4())
    appr_id = uuid4()

    event = audit_service.record_deployment_event(
        deployment_id=dep_id,
        workflow_id=wf_id,
        version_number=1,
        environment="production",
        actor="deployer_bot",
        approval_id=appr_id,
        status="SUCCESS",
        correlation_id="cid-deploy-789",
    )

    assert event.event_type == "deployment.executed"
    assert event.target_type == "deployment"
    assert event.target_id == dep_id
    assert event.metadata["workflow_id"] == wf_id
    assert event.metadata["approval_id"] == str(appr_id)
    assert event.outcome == "SUCCESS"


# Acceptance Criterion 5: Provider operations record duration, outcome, and errors
def test_record_provider_operation(audit_service):
    event = audit_service.record_provider_operation(
        provider_name="n8n",
        operation_name="trigger_webhook",
        target_id="hook-lead-sync",
        actor="test_runner",
        outcome="SUCCESS",
        duration_ms=124.5,
        correlation_id="cid-prov-001",
    )
    assert event.event_type == "provider.operation"
    assert event.target_type == "n8n.operation"
    assert event.target_id == "hook-lead-sync"
    assert event.metadata["duration_ms"] == 124.5


# Acceptance Criterion 6: Sensitive credentials in audit metadata are scrubbed recursively
def test_audit_metadata_scrubs_secrets(audit_service):
    event = audit_service.record_workflow_mutation(
        mutation_type="created",
        workflow_id="wf-test-secret",
        actor="user",
        version_number=1,
        after_state={
            "api_key": "raw_secret_api_key_12345",
            "db": {"password": "SuperSecretDbPassword!"},
        },
    )
    # The hash should be computed from raw state, but metadata attached to AuditEvent must be scrubbed
    secret_event = AuditEvent(
        event_type="test.secret",
        actor="user",
        target_type="test",
        target_id="1",
        metadata={
            "apiKey": "very_secret_api_key",
            "nested": {"token": "bearer_xyz_789"},
            "safe_key": "safe_value",
        },
    )
    assert secret_event.metadata["apiKey"] == "********"
    assert secret_event.metadata["nested"]["token"] == "********"
    assert secret_event.metadata["safe_key"] == "safe_value"


# Querying buffered events by target
def test_list_by_target(audit_service):
    target_a = str(uuid4())
    target_b = str(uuid4())

    audit_service.record_workflow_mutation("created", target_a, "alice", 1)
    audit_service.record_workflow_mutation("updated", target_a, "alice", 2)
    audit_service.record_workflow_mutation("created", target_b, "bob", 1)

    events_a = audit_service.list_by_target("workflow", target_a)
    events_b = audit_service.list_by_target("workflow", target_b)

    assert len(events_a) == 2
    assert len(events_b) == 1
    assert len(audit_service.get_buffered_events()) == 3
