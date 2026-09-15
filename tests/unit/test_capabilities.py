"""Unit tests for capability registry and truthfulness."""

from app.domain.capabilities.models import CapabilityRegistry, CapabilityStatus, get_default_n8n_registry


def test_default_n8n_registry_classifications():
    registry = get_default_n8n_registry()

    # Native direct execution must be UNSUPPORTED
    native_exec = registry.get("workflow.execute.native")
    assert native_exec is not None
    assert native_exec.status == CapabilityStatus.UNSUPPORTED
    assert not registry.is_supported("workflow.execute.native")

    # Webhook execution must be WORKAROUND_AVAILABLE
    webhook_exec = registry.get("workflow.execute.webhook")
    assert webhook_exec is not None
    assert webhook_exec.status == CapabilityStatus.WORKAROUND_AVAILABLE
    assert registry.is_workaround("workflow.execute.webhook")
    assert webhook_exec.workaround_id == "N8N-WA-001"

    # OpenAPI must be KNOWN_LIMITATION
    openapi_cap = registry.get("openapi.specification")
    assert openapi_cap is not None
    assert openapi_cap.status == CapabilityStatus.KNOWN_LIMITATION

    # Internal python runner must be KNOWN_LIMITATION
    py_runner = registry.get("runner.python.internal")
    assert py_runner is not None
    assert py_runner.status == CapabilityStatus.KNOWN_LIMITATION

    # Core workflow management is RUNTIME_VERIFIED
    assert registry.is_supported("instance.connectivity")
    assert registry.is_supported("workflow.list")
    assert registry.is_supported("workflow.create")
