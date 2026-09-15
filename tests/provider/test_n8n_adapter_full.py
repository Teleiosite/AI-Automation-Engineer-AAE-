"""Comprehensive contract tests for N8nProvider adapter implementation."""

from unittest.mock import MagicMock
import pytest

from app.providers.base import AutomationProvider
from app.providers.models import (
    ProviderExecution,
    ProviderExecutionResult,
    ProviderInstanceInfo,
    ProviderValidationResult,
    ProviderWorkflow,
)
from app.providers.n8n.adapter import N8nProvider
from app.providers.n8n.client import N8nClient


@pytest.fixture
def mock_client():
    return MagicMock(spec=N8nClient)


@pytest.fixture
def provider(mock_client):
    mock_client.base_url = "http://localhost:5678"
    return N8nProvider(client=mock_client)


def test_provider_instance_info(provider, mock_client):
    mock_client.get_instance_info.return_value = {"status": "ok", "version": "2.38.7"}
    info = provider.get_instance_info()
    assert isinstance(info, ProviderInstanceInfo)
    assert info.provider == "n8n"
    assert info.version == "2.38.7"
    assert info.status == "healthy"
    assert info.features["webhook_execution"] is True
    assert info.features["direct_execution"] is False


def test_provider_list_workflows(provider, mock_client):
    mock_client.list_workflows.return_value = {
        "data": [
            {
                "id": "wf-1",
                "name": "Sync Lead Workflow",
                "active": True,
                "versionId": "v-1",
                "nodes": [{"name": "Start", "type": "n8n-nodes-base.manualTrigger"}],
                "connections": {},
                "createdAt": "2026-09-14T20:00:00.000Z",
                "updatedAt": "2026-09-14T20:30:00.000Z",
            }
        ]
    }
    workflows = provider.list_workflows(limit=10)
    assert len(workflows) == 1
    wf = workflows[0]
    assert isinstance(wf, ProviderWorkflow)
    assert wf.id == "wf-1"
    assert wf.name == "Sync Lead Workflow"
    assert wf.active is True
    assert wf.created_at is not None


def test_provider_create_workflow(provider, mock_client):
    mock_client.create_workflow.return_value = {
        "id": "wf-new",
        "name": "New Automation",
        "active": False,
        "nodes": [{"name": "Node 1", "type": "n8n-nodes-base.set"}],
        "connections": {},
    }
    wf = provider.create_workflow(
        name="New Automation",
        nodes=[{"name": "Node 1", "type": "n8n-nodes-base.set"}],
        connections={},
    )
    assert isinstance(wf, ProviderWorkflow)
    assert wf.id == "wf-new"
    assert wf.name == "New Automation"
    assert wf.active is False


def test_provider_update_and_lifecycle(provider, mock_client):
    mock_client.get_workflow.return_value = {
        "id": "wf-1",
        "name": "Old Name",
        "active": False,
        "nodes": [],
        "connections": {},
    }
    mock_client.update_workflow.return_value = {
        "id": "wf-1",
        "name": "Updated Name",
        "active": False,
        "nodes": [],
        "connections": {},
    }
    mock_client.activate_workflow.return_value = {
        "id": "wf-1",
        "name": "Updated Name",
        "active": True,
        "nodes": [],
        "connections": {},
    }
    mock_client.deactivate_workflow.return_value = {
        "id": "wf-1",
        "name": "Updated Name",
        "active": False,
        "nodes": [],
        "connections": {},
    }
    mock_client.delete_workflow.return_value = True

    updated = provider.update_workflow("wf-1", name="Updated Name")
    assert updated.name == "Updated Name"

    activated = provider.activate_workflow("wf-1")
    assert activated.active is True

    deactivated = provider.deactivate_workflow("wf-1")
    assert deactivated.active is False

    deleted = provider.delete_workflow("wf-1")
    assert deleted is True


def test_provider_execution_history(provider, mock_client):
    mock_client.list_executions.return_value = {
        "data": [
            {
                "id": "exec-1",
                "workflowId": "wf-1",
                "status": "success",
                "startedAt": "2026-09-14T21:00:00.000Z",
                "stoppedAt": "2026-09-14T21:00:02.500Z",
                "mode": "webhook",
            }
        ]
    }
    mock_client.get_execution.return_value = {
        "id": "exec-1",
        "workflowId": "wf-1",
        "status": "success",
        "startedAt": "2026-09-14T21:00:00.000Z",
        "stoppedAt": "2026-09-14T21:00:02.500Z",
        "mode": "webhook",
        "data": {"resultData": {"runData": {}}},
    }
    mock_client.retry_execution.return_value = {
        "id": "exec-2",
        "workflowId": "wf-1",
        "status": "running",
        "retryOf": "exec-1",
    }

    execs = provider.list_executions(workflow_id="wf-1")
    assert len(execs) == 1
    assert isinstance(execs[0], ProviderExecution)
    assert execs[0].id == "exec-1"
    assert execs[0].duration_ms == 2500.0

    single = provider.get_execution("exec-1")
    assert single.status == "success"
    assert single.data is not None

    retried = provider.retry_execution("exec-1")
    assert retried.retry_of == "exec-1"


def test_provider_validate_workflow_valid(provider):
    valid_data = {
        "nodes": [
            {"name": "Trigger", "type": "n8n-nodes-base.webhook", "typeVersion": 1, "position": [100, 100]},
            {"name": "Process", "type": "n8n-nodes-base.set", "typeVersion": 2, "position": [300, 100]},
        ],
        "connections": {
            "Trigger": {
                "main": [[{"node": "Process", "type": "main", "index": 0}]]
            }
        }
    }
    result = provider.validate_workflow(valid_data)
    assert isinstance(result, ProviderValidationResult)
    assert result.is_valid is True
    assert len(result.errors) == 0


def test_provider_validate_workflow_invalid(provider):
    # Missing type, broken connection
    invalid_data = {
        "nodes": [
            {"name": "Node A", "position": [100, 100]},  # missing type
        ],
        "connections": {
            "Node A": {
                "main": [[{"node": "NonExistentTarget", "type": "main", "index": 0}]]
            }
        }
    }
    result = provider.validate_workflow(invalid_data)
    assert result.is_valid is False
    assert any("missing required 'type'" in err for err in result.errors)
    assert any("references non-existent target 'NonExistentTarget'" in err for err in result.errors)


def test_provider_security_audit_detects_plaintext_secret_and_dangerous_nodes(provider):
    unsafe_data = {
        "nodes": [
            {
                "name": "Bash Exec",
                "type": "n8n-nodes-base.executeCommand",
                "parameters": {"command": "rm -rf /tmp"},
            },
            {
                "name": "Insecure Webhook",
                "type": "n8n-nodes-base.webhook",
                "parameters": {
                    "path": "public-hook",
                    "authentication": "none",
                    "api_key": "raw_plaintext_key_value_123",
                },
            },
        ]
    }
    audit = provider.security_audit(unsafe_data)
    assert audit["status"] == "FLAGGED"
    assert audit["risk_level"] == "CRITICAL"
    findings = audit["findings"]
    assert any(f["severity"] == "CRITICAL" and "Arbitrary command execution" in f["issue"] for f in findings)
    assert any(f["severity"] == "MEDIUM" and "no authentication" in f["issue"] for f in findings)
    assert any(f["severity"] == "HIGH" and "Plaintext credential" in f["issue"] for f in findings)
