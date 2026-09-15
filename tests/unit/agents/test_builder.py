"""Unit tests for WorkflowBuilder, connection graph compilation, and secret hygiene (Phase 11)."""

from uuid import uuid4
import pytest

from app.domain.enums import WorkflowStatus, WorkflowVersionStatus
from app.domain.errors import DomainValidationError, InvariantViolationError
from app.domain.models.workflow import Workflow, WorkflowVersion
from app.domain.services.audit_service import AuditService
from app.domain.services.workflow_builder import WorkflowBuilder
from app.domain.services.workflow_planner import PlannedConnection, PlannedNode, WorkflowPlan
from app.agents.builder import Builder


@pytest.fixture
def recorded_events():
    events = []
    def sink(event):
        events.append(event)
    return events, sink


@pytest.fixture
def audit_service(recorded_events):
    _, sink = recorded_events
    return AuditService(sink=sink)


@pytest.fixture
def builder(audit_service) -> WorkflowBuilder:
    return WorkflowBuilder(audit_service=audit_service)


@pytest.fixture
def sample_plan() -> WorkflowPlan:
    nodes = (
        PlannedNode(
            node_id="node_trigger",
            name="Webhook Trigger",
            node_type="n8n-nodes-base.webhook",
            type_version=2.0,
            parameters={"path": "lead", "httpMethod": "POST"},
        ),
        PlannedNode(
            node_id="node_postgres_1",
            name="PostgreSQL Leads",
            node_type="n8n-nodes-base.postgres",
            type_version=2.5,
            parameters={"operation": "insert", "table": "leads"},
            retry_on_fail=True,
            max_retries=3,
        ),
        PlannedNode(
            node_id="node_ext_service_1",
            name="Send Email (SMTP)",
            node_type="n8n-nodes-base.emailSend",
            type_version=2.1,
            parameters={"subject": "Enquiry Received", "to": "={{ $json.email }}"},
            retry_on_fail=True,
            max_retries=3,
        ),
    )
    connections = (
        PlannedConnection(source_node="node_trigger", target_node="node_postgres_1"),
        PlannedConnection(source_node="node_postgres_1", target_node="node_ext_service_1"),
    )
    return WorkflowPlan(
        plan_id=uuid4(),
        specification_id=uuid4(),
        specification_version=1,
        workflow_name="Lead Capture Pipeline",
        nodes=nodes,
        connections=connections,
        data_stores=("PostgreSQL",),
        external_services=("Email",),
        has_destructive_operations=False,
        planned_actions=("Persist record to PostgreSQL", "Dispatch outbound message via Email"),
        test_scenarios=("Verify lead insertion", "Verify confirmation email"),
    )


# 1. Happy Path: Plan to canonical n8n JSON definition
def test_builder_happy_path(builder, sample_plan):
    definition = builder.build_workflow_definition(sample_plan)

    assert definition["name"] == "Lead Capture Pipeline"
    assert len(definition["nodes"]) == 3
    assert "connections" in definition

    # Verify node structure and spacing
    nodes = definition["nodes"]
    assert nodes[0]["name"] == "Webhook Trigger"
    assert nodes[0]["position"] == [250, 300]
    assert nodes[1]["position"] == [500, 300]
    assert nodes[2]["position"] == [750, 300]

    # Node retry properties
    assert nodes[1]["retryOnFail"] is True
    assert nodes[1]["maxTries"] == 3

    # Verify connection graph
    conns = definition["connections"]
    assert "Webhook Trigger" in conns
    assert conns["Webhook Trigger"]["main"][0][0]["node"] == "PostgreSQL Leads"

    assert "PostgreSQL Leads" in conns
    assert conns["PostgreSQL Leads"]["main"][0][0]["node"] == "Send Email (SMTP)"

    # Verify settings & meta
    assert definition["settings"]["saveDataErrorExecution"] == "all"
    assert definition["meta"]["specificationVersion"] == 1


# 2. Build full Workflow aggregate and version
def test_build_workflow_aggregate(builder, sample_plan, recorded_events):
    events, _ = recorded_events
    project_id = uuid4()

    workflow, version = builder.build_workflow(sample_plan, project_id=project_id)

    assert workflow.name == "Lead Capture Pipeline"
    assert workflow.project_id == project_id
    assert workflow.status == WorkflowStatus.DRAFT
    assert len(workflow.versions) == 1

    assert version.version_number == 1
    assert version.status == WorkflowVersionStatus.DRAFT
    assert version.definition["name"] == "Lead Capture Pipeline"

    # Audit event recorded
    assert any(e.event_type == "workflow.built" for e in events)


# 3. Secret Scrubber rejects hardcoded plaintext credentials
def test_builder_rejects_hardcoded_secrets(builder):
    compromised_nodes = (
        PlannedNode(
            node_id="node_1",
            name="Insecure API",
            node_type="n8n-nodes-base.httpRequest",
            type_version=1.0,
            parameters={"password": "super_secret_plain_text_password"},
        ),
    )
    plan = WorkflowPlan(
        plan_id=uuid4(),
        specification_id=uuid4(),
        specification_version=1,
        workflow_name="Insecure",
        nodes=compromised_nodes,
        connections=(),
        data_stores=(),
        external_services=(),
        has_destructive_operations=False,
        planned_actions=(),
        test_scenarios=(),
    )

    with pytest.raises(DomainValidationError, match="Prohibited hardcoded secret"):
        builder.build_workflow_definition(plan)


# 4. Expressions are allowed for secrets
def test_builder_allows_credential_expressions(builder):
    safe_nodes = (
        PlannedNode(
            node_id="node_1",
            name="Secure API",
            node_type="n8n-nodes-base.httpRequest",
            type_version=1.0,
            parameters={"password": "={{ $env.SECURE_PASSWORD }}"},
        ),
    )
    plan = WorkflowPlan(
        plan_id=uuid4(),
        specification_id=uuid4(),
        specification_version=1,
        workflow_name="Secure",
        nodes=safe_nodes,
        connections=(),
        data_stores=(),
        external_services=(),
        has_destructive_operations=False,
        planned_actions=(),
        test_scenarios=(),
    )

    definition = builder.build_workflow_definition(plan)
    assert definition["nodes"][0]["parameters"]["password"] == "={{ $env.SECURE_PASSWORD }}"


# 5. Append new version to existing workflow
def test_builder_appends_version_to_existing_workflow(builder, sample_plan):
    project_id = uuid4()
    workflow, ver1 = builder.build_workflow(sample_plan, project_id=project_id)

    # Build second version
    workflow, ver2 = builder.build_workflow(sample_plan, project_id=project_id, workflow=workflow)

    assert ver2.version_number == 2
    assert len(workflow.versions) == 2
    assert ver1.version_number == 1


# 6. Builder Agent Component
def test_builder_agent_component(builder, sample_plan):
    agent_builder = Builder(builder_service=builder)
    project_id = uuid4()

    wf, ver = agent_builder.build(sample_plan, project_id=project_id)

    assert wf is not None
    assert ver.version_number == 1
    assert len(ver.definition["nodes"]) == 3
