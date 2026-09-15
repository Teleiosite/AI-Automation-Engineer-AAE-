"""Unit tests for WorkflowValidator service and Validator agent component (Phase 12)."""

from uuid import uuid4
import pytest

from app.agents.validator import Validator
from app.domain.enums import RequirementType, RiskLevel, SpecificationStatus
from app.domain.models.specification import Specification, SpecificationVersion
from app.domain.models.workflow import Workflow
from app.domain.services.workflow_builder import WorkflowBuilder
from app.domain.services.workflow_planner import (
    PlannedConnection,
    PlannedNode,
    WorkflowPlan,
)
from app.domain.services.workflow_validator import (
    ValidationCategory,
    ValidationReport,
    ValidationSeverity,
    WorkflowValidator,
)


@pytest.fixture
def sample_valid_definition() -> dict:
    """Canonical valid n8n workflow definition."""
    return {
        "name": "Customer Lead Sync",
        "nodes": [
            {
                "id": "node-1",
                "name": "Webhook Trigger",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 1,
                "position": [250, 300],
                "parameters": {
                    "path": "lead-sync",
                    "httpMethod": "POST",
                },
            },
            {
                "id": "node-2",
                "name": "Postgres Store",
                "type": "n8n-nodes-base.postgres",
                "typeVersion": 1,
                "position": [500, 300],
                "parameters": {
                    "operation": "insert",
                    "table": "leads",
                    "data": "={{ $json.body }}",
                },
            },
        ],
        "connections": {
            "Webhook Trigger": {
                "main": [
                    [
                        {"node": "Postgres Store", "type": "main", "index": 0}
                    ]
                ]
            }
        },
        "settings": {"saveExecutionProgress": True},
    }


def test_validator_happy_path(sample_valid_definition):
    validator = WorkflowValidator()
    report = validator.validate(sample_valid_definition)

    assert report.is_valid is True
    assert report.error_count == 0
    assert report.critical_count == 0
    assert report.workflow_name == "Customer Lead Sync"
    assert not report.has_errors()
    assert not report.has_critical()


def test_validator_schema_violations():
    validator = WorkflowValidator()

    # Non-dict definition
    rep1 = validator.validate("not-a-dict")
    assert rep1.is_valid is False
    assert rep1.has_critical()
    assert any(i.rule_id == "SCH-001" for i in rep1.issues)

    # Missing nodes
    rep2 = validator.validate({"connections": {}})
    assert rep2.is_valid is False
    assert any(i.rule_id == "SCH-002" for i in rep2.issues)

    # Missing connections
    rep3 = validator.validate({"nodes": [{"id": "1", "name": "n", "type": "t", "typeVersion": 1}]})
    assert any(i.rule_id == "SCH-003" for i in rep3.issues)

    # Malformed node
    rep4 = validator.validate({
        "nodes": [
            {"id": "1", "name": None, "type": 123, "typeVersion": -1}
        ],
        "connections": {},
    })
    assert any(i.rule_id == "SCH-005" for i in rep4.issues)
    assert any(i.rule_id == "NOD-001" for i in rep4.issues)
    assert any(i.rule_id == "NOD-002" for i in rep4.issues)


def test_validator_structural_violations(sample_valid_definition):
    validator = WorkflowValidator()

    # Empty nodes
    rep_empty = validator.validate({"nodes": [], "connections": {}})
    assert any(i.rule_id == "STR-003" for i in rep_empty.issues)

    # Duplicate node names
    dup_names = {
        "nodes": [
            {"id": "1", "name": "Step A", "type": "n8n-nodes-base.webhook", "typeVersion": 1, "parameters": {"path": "p"}},
            {"id": "2", "name": "Step A", "type": "n8n-nodes-base.postgres", "typeVersion": 1, "parameters": {"operation": "insert"}},
        ],
        "connections": {},
    }
    rep_dup = validator.validate(dup_names)
    assert any(i.rule_id == "STR-001" for i in rep_dup.issues)

    # Missing trigger node
    no_trigger = {
        "nodes": [
            {"id": "1", "name": "Worker 1", "type": "n8n-nodes-base.httpRequest", "typeVersion": 1, "parameters": {"url": "https://api.test/data"}},
            {"id": "2", "name": "Worker 2", "type": "n8n-nodes-base.postgres", "typeVersion": 1, "parameters": {"operation": "insert"}},
        ],
        "connections": {
            "Worker 1": {"main": [[{"node": "Worker 2", "type": "main", "index": 0}]]}
        },
    }
    rep_no_trig = validator.validate(no_trigger)
    assert any(i.rule_id == "STR-004" for i in rep_no_trig.issues)

    # Orphan non-trigger node & disconnected node
    orphaned = {
        "nodes": [
            {"id": "1", "name": "Webhook", "type": "n8n-nodes-base.webhook", "typeVersion": 1, "parameters": {"path": "p"}},
            {"id": "2", "name": "Store", "type": "n8n-nodes-base.postgres", "typeVersion": 1, "parameters": {"operation": "insert"}},
            {"id": "3", "name": "Isolated Node", "type": "n8n-nodes-base.httpRequest", "typeVersion": 1, "parameters": {"url": "https://api.test/data"}},
        ],
        "connections": {
            "Webhook": {"main": [[{"node": "Store", "type": "main", "index": 0}]]}
        },
    }
    rep_orphan = validator.validate(orphaned)
    assert any(i.rule_id == "STR-005" for i in rep_orphan.issues)


def test_validator_connection_violations():
    validator = WorkflowValidator()

    # Connection to non-existent target
    invalid_target = {
        "nodes": [
            {"id": "1", "name": "Trigger", "type": "n8n-nodes-base.webhook", "typeVersion": 1, "parameters": {"path": "p"}},
        ],
        "connections": {
            "Trigger": {"main": [[{"node": "Ghost Node", "type": "main", "index": 0}]]}
        },
    }
    rep = validator.validate(invalid_target)
    assert any(i.rule_id == "CON-004" for i in rep.issues)

    # Self loop
    self_loop = {
        "nodes": [
            {"id": "1", "name": "LoopNode", "type": "n8n-nodes-base.webhook", "typeVersion": 1, "parameters": {"path": "p"}},
        ],
        "connections": {
            "LoopNode": {"main": [[{"node": "LoopNode", "type": "main", "index": 0}]]}
        },
    }
    rep_loop = validator.validate(self_loop)
    assert any(i.rule_id == "CON-005" for i in rep_loop.issues)


def test_validator_configuration_violations():
    validator = WorkflowValidator()

    bad_config = {
        "nodes": [
            {"id": "1", "name": "Empty Webhook", "type": "n8n-nodes-base.webhook", "typeVersion": 1, "parameters": {"path": ""}},
            {"id": "2", "name": "Empty HTTP", "type": "n8n-nodes-base.httpRequest", "typeVersion": 1, "parameters": {}},
            {"id": "3", "name": "Empty Postgres", "type": "n8n-nodes-base.postgres", "typeVersion": 1, "parameters": {}},
            {"id": "4", "name": "Empty Schedule", "type": "n8n-nodes-base.scheduleTrigger", "typeVersion": 1, "parameters": {}},
        ],
        "connections": {},
    }
    rep = validator.validate(bad_config)
    assert any(i.rule_id == "CFG-002" for i in rep.issues)
    assert any(i.rule_id == "CFG-003" for i in rep.issues)
    assert any(i.rule_id == "CFG-004" for i in rep.issues)
    assert any(i.rule_id == "CFG-005" for i in rep.issues)


def test_validator_expression_violations():
    validator = WorkflowValidator()

    bad_expressions = {
        "nodes": [
            {
                "id": "1",
                "name": "Webhook",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 1,
                "parameters": {"path": "test"},
            },
            {
                "id": "2",
                "name": "Processor",
                "type": "n8n-nodes-base.httpRequest",
                "typeVersion": 1,
                "parameters": {
                    "url": "https://api.example.com",
                    "unbalanced": "={{ $json.missing_brace }",
                    "empty": "={{  }}",
                },
            },
        ],
        "connections": {
            "Webhook": {"main": [[{"node": "Processor", "type": "main", "index": 0}]]}
        },
    }
    rep = validator.validate(bad_expressions)
    assert any(i.rule_id == "EXP-001" for i in rep.issues)
    assert any(i.rule_id == "EXP-002" for i in rep.issues)


def test_validator_security_violations():
    validator = WorkflowValidator()

    insecure_wf = {
        "nodes": [
            {
                "id": "1",
                "name": "Webhook",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 1,
                "parameters": {"path": "hook"},
            },
            {
                "id": "2",
                "name": "Insecure HTTP",
                "type": "n8n-nodes-base.httpRequest",
                "typeVersion": 1,
                "parameters": {
                    "url": "http://api.external-service.com/data",
                    "api_key": "raw-unencrypted-secret-key-12345",
                },
            },
            {
                "id": "3",
                "name": "Dangerous SQL",
                "type": "n8n-nodes-base.postgres",
                "typeVersion": 1,
                "parameters": {
                    "operation": "executeQuery",
                    "query": "DROP TABLE users;",
                },
            },
        ],
        "connections": {
            "Webhook": {"main": [[{"node": "Insecure HTTP", "type": "main", "index": 0}]]},
            "Insecure HTTP": {"main": [[{"node": "Dangerous SQL", "type": "main", "index": 0}]]},
        },
    }
    rep = validator.validate(insecure_wf)

    assert rep.is_valid is False
    assert rep.has_critical()
    assert any(i.rule_id == "SEC-001" for i in rep.issues)  # Plaintext secret
    assert any(i.rule_id == "SEC-002" for i in rep.issues)  # Insecure HTTP
    assert any(i.rule_id == "SEC-003" for i in rep.issues)  # Destructive SQL


def test_validator_semantic_and_specification_mapping():
    validator = WorkflowValidator()

    spec = Specification(
        project_id=uuid4(),
        requirement_id=uuid4(),
    )
    spec.add_version({
        "title": "Scheduled Email Digest",
        "business_objective": "Send daily summary emails",
        "scope_inclusions": ["cron trigger", "PostgreSQL query", "send email"],
        "scope_exclusions": [],
        "trigger": "Daily at 08:00 AM (cron schedule)",
        "inputs": [],
        "outputs": ["Email notification"],
        "external_systems": ["PostgreSQL", "Email"],
        "risk_level": RiskLevel.MEDIUM.value,
        "success_criteria": ["Email delivered successfully"],
    })

    # Built workflow only has Webhook and HTTP Request (missing Schedule, Postgres, Email)
    mismatched_wf = {
        "nodes": [
            {
                "id": "1",
                "name": "Webhook Trigger",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 1,
                "parameters": {"path": "test"},
            },
            {
                "id": "2",
                "name": "HTTP Node",
                "type": "n8n-nodes-base.httpRequest",
                "typeVersion": 1,
                "parameters": {"url": "https://api.example.com"},
            },
        ],
        "connections": {
            "Webhook Trigger": {"main": [[{"node": "HTTP Node", "type": "main", "index": 0}]]}
        },
    }

    rep = validator.validate(mismatched_wf, specification=spec)

    assert rep.is_valid is False
    # SEM-001: Missing schedule trigger
    assert any(i.rule_id == "SEM-001" for i in rep.issues)
    # SEM-003: Missing postgres
    assert any(i.rule_id == "SEM-003" for i in rep.issues)
    # SEM-004: Missing email
    assert any(i.rule_id == "SEM-004" for i in rep.issues)


def test_validator_agent_component(sample_valid_definition):
    validator_agent = Validator()

    # Validate raw dict
    rep1 = validator_agent.validate(sample_valid_definition)
    assert rep1.is_valid is True

    # Validate Workflow aggregate
    wf = Workflow(project_id=uuid4(), name="Test Workflow")
    wf.add_version(
        specification_version_id=uuid4(),
        definition=sample_valid_definition,
        change_reason="Initial compile",
    )

    rep2 = validator_agent.validate_workflow(wf)
    assert rep2.is_valid is True
    assert rep2.workflow_name == "Customer Lead Sync"
    assert rep2.error_count == 0
