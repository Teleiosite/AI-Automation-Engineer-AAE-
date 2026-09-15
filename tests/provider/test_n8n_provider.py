"""Provider tests for n8n adapter and execution routing."""

from unittest.mock import MagicMock
import pytest
from app.providers.base import AutomationProvider, CapabilityLimitationError
from app.providers.n8n.adapter import N8nProvider
from app.providers.n8n.client import N8nClient


def test_provider_interface_conformance():
    provider = N8nProvider()
    assert isinstance(provider, AutomationProvider)
    assert provider.name == "n8n"
    assert provider.version == "2.38.7"


def test_execute_workflow_rejects_workflow_without_webhook():
    mock_client = MagicMock(spec=N8nClient)
    # Return workflow with only manual / schedule trigger
    mock_client.get_workflow.return_value = {
        "id": "wf-123",
        "name": "Schedule Only Workflow",
        "nodes": [
            {"name": "Schedule Trigger", "type": "n8n-nodes-base.scheduleTrigger"}
        ]
    }
    provider = N8nProvider(client=mock_client)

    # Must raise CapabilityLimitationError per ADR 0002
    with pytest.raises(CapabilityLimitationError) as exc_info:
        provider.execute_workflow("wf-123", payload={"data": 1})

    assert "lacks a compatible webhook trigger node" in str(exc_info.value)
    mock_client.trigger_webhook.assert_not_called()


def test_execute_workflow_triggers_webhook_when_available():
    mock_client = MagicMock(spec=N8nClient)
    mock_client.get_workflow.return_value = {
        "id": "wf-webhook-1",
        "name": "Webhook Workflow",
        "nodes": [
            {
                "name": "Webhook Node",
                "type": "n8n-nodes-base.webhook",
                "parameters": {
                    "path": "test-hook",
                    "httpMethod": "POST"
                }
            }
        ]
    }
    mock_client.trigger_webhook.return_value = {"success": True, "executionId": "exec-999"}

    provider = N8nProvider(client=mock_client)
    result = provider.execute_workflow("wf-webhook-1", payload={"test": "payload"})

    assert result["execution_status"] == "initiated"
    assert result["mechanism"] == "workaround"
    assert result["workaround_id"] == "N8N-WA-001"
    assert result["webhook_path"] == "test-hook"
    mock_client.trigger_webhook.assert_called_once_with(
        webhook_path="test-hook",
        payload={"test": "payload"},
        method="POST",
    )
