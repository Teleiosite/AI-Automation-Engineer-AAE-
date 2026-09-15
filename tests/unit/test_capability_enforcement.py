"""Tests for Capability Registry, CapabilityEnforcementService, and Repository (Phase 4)."""

import pytest
from app.domain.capabilities.models import (
    Capability,
    CapabilityDecision,
    CapabilityEvidence,
    CapabilityRegistry,
    CapabilityStatus,
    get_default_n8n_registry,
)
from app.domain.capabilities.repository import CapabilityRepository
from app.domain.capabilities.service import (
    CapabilityEnforcementError,
    CapabilityEnforcementService,
)


@pytest.fixture
def registry():
    return get_default_n8n_registry()


@pytest.fixture
def enforcer(registry):
    return CapabilityEnforcementService(registry)


@pytest.fixture
def repo(registry):
    return CapabilityRepository(registry)


# Acceptance Criterion 1: UNKNOWN operations cannot execute
def test_unknown_operation_evaluation_is_blocked(enforcer):
    decision = enforcer.evaluate("workflow.delete")
    assert decision.allowed is False
    assert decision.status == CapabilityStatus.UNKNOWN
    assert "UNKNOWN" in decision.reason
    assert decision.required_action is not None

    with pytest.raises(CapabilityEnforcementError) as exc_info:
        enforcer.enforce("workflow.delete")
    assert "status is UNKNOWN" in str(exc_info.value)


# Acceptance Criterion 2: UNSUPPORTED operations cannot execute
def test_unsupported_operation_evaluation_is_blocked(enforcer):
    decision = enforcer.evaluate("workflow.execute.native")
    assert decision.allowed is False
    assert decision.status == CapabilityStatus.UNSUPPORTED
    assert "UNSUPPORTED" in decision.reason
    assert "Do not execute" in decision.required_action

    with pytest.raises(CapabilityEnforcementError) as exc_info:
        enforcer.enforce("workflow.execute.native")
    assert "UNSUPPORTED" in str(exc_info.value)


# Acceptance Criterion 3: Unregistered operations are treated as UNKNOWN and blocked
def test_unregistered_operation_is_blocked(enforcer):
    decision = enforcer.evaluate("hypothetical.future.feature")
    assert decision.allowed is False
    assert decision.status == CapabilityStatus.UNKNOWN
    assert "not registered" in decision.reason

    with pytest.raises(CapabilityEnforcementError) as exc_info:
        enforcer.enforce("hypothetical.future.feature")
    assert "not registered" in str(exc_info.value)


# Acceptance Criterion 4: KNOWN_LIMITATION operations cannot execute natively
def test_known_limitation_is_blocked(enforcer):
    decision = enforcer.evaluate("openapi.specification")
    assert decision.allowed is False
    assert decision.status == CapabilityStatus.KNOWN_LIMITATION

    with pytest.raises(CapabilityEnforcementError) as exc_info:
        enforcer.enforce("openapi.specification")
    assert "KNOWN_LIMITATION" in str(exc_info.value)


# Acceptance Criterion 5: WORKAROUND_AVAILABLE is denied natively but points to workaround
def test_workaround_available_evaluation(enforcer):
    decision = enforcer.evaluate("workflow.execute.webhook")
    assert decision.allowed is False
    assert decision.status == CapabilityStatus.WORKAROUND_AVAILABLE
    assert decision.workaround_id == "N8N-WA-001"
    assert "verified workaround 'N8N-WA-001' is required" in decision.reason


# Acceptance Criterion 6: Verified operations are permitted
def test_verified_operations_are_allowed(enforcer):
    for op in [
        "instance.connectivity",
        "auth.api_key",
        "workflow.list",
        "workflow.get",
        "workflow.create",
        "workflow.update",
        "workflow.activate",
        "workflow.deactivate",
        "execution.list",
        "execution.get",
        "failure.inspect",
        "workflow.repair",
    ]:
        decision = enforcer.evaluate(op)
        assert decision.allowed is True
        assert decision.status == CapabilityStatus.RUNTIME_VERIFIED
        # enforce should not raise
        result = enforcer.enforce(op)
        assert result.allowed is True


# Evidence Attachment & Status Promotion
def test_record_evidence_and_status_promotion(enforcer):
    # Initially UNKNOWN
    decision = enforcer.evaluate("execution.retry")
    assert decision.allowed is False

    # Attach verification evidence and promote to RUNTIME_VERIFIED
    evidence = CapabilityEvidence(
        evidence_type="integration_test",
        details="POST /api/v1/executions/123/retry successfully restarted execution",
    )
    enforcer.update_status("execution.retry", CapabilityStatus.RUNTIME_VERIFIED, evidence)

    # Now should be allowed
    new_decision = enforcer.evaluate("execution.retry")
    assert new_decision.allowed is True
    assert new_decision.status == CapabilityStatus.RUNTIME_VERIFIED


# CapabilityRepository tests
def test_capability_repository_crud(repo):
    all_caps = repo.list_all()
    assert len(all_caps) >= 20

    verified_caps = repo.list_by_status(CapabilityStatus.RUNTIME_VERIFIED)
    assert len(verified_caps) >= 12

    unsupported_caps = repo.list_by_status(CapabilityStatus.UNSUPPORTED)
    assert any(c.name == "workflow.execute.native" for c in unsupported_caps)

    # Custom capability save & delete
    custom = Capability(name="test.op", status=CapabilityStatus.DOCUMENTED)
    repo.save(custom)
    assert repo.get("test.op") is not None
    assert repo.delete("test.op") is True
    assert repo.get("test.op") is None
