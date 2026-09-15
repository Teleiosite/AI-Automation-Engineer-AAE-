"""Comprehensive test suite for Deterministic Security Policy Engine and Risk Classifier (Phase 5)."""

import pytest
from app.domain.capabilities.models import CapabilityStatus, get_default_n8n_registry
from app.domain.policy.classifier import RiskClassifier
from app.domain.policy.engine import PolicyEngine, PolicyViolationError
from app.domain.policy.models import (
    Environment,
    PolicyAction,
    PolicyDecisionType,
    RiskLevel,
    SecurityContext,
    UserRole,
)


@pytest.fixture
def registry():
    return get_default_n8n_registry()


@pytest.fixture
def policy_engine(registry):
    return PolicyEngine(capability_registry=registry)


# 1. Authentication Tests
def test_unauthenticated_actor_is_denied(policy_engine):
    ctx = SecurityContext(
        actor_id="anonymous",
        role=UserRole.ENGINEER,
        authenticated=False,
    )
    decision = policy_engine.evaluate(PolicyAction.READ, ctx)
    assert decision.decision == PolicyDecisionType.DENY
    assert "not authenticated" in decision.reason

    with pytest.raises(PolicyViolationError) as exc_info:
        policy_engine.enforce(PolicyAction.READ, ctx)
    assert "Actor is not authenticated" in str(exc_info.value)


# 2. Capability Status Tests
def test_unknown_capability_yields_require_verification(policy_engine):
    ctx = SecurityContext(actor_id="eng-1", role=UserRole.ENGINEER, environment=Environment.DEVELOPMENT)
    decision = policy_engine.evaluate(
        action=PolicyAction.EXECUTE,
        security_context=ctx,
        capability_name="execution.retry",  # UNKNOWN in registry
    )
    assert decision.decision == PolicyDecisionType.REQUIRE_VERIFICATION
    assert "UNKNOWN" in decision.reason


def test_unsupported_capability_yields_deny(policy_engine):
    ctx = SecurityContext(actor_id="eng-1", role=UserRole.ENGINEER, environment=Environment.DEVELOPMENT)
    decision = policy_engine.evaluate(
        action=PolicyAction.EXECUTE,
        security_context=ctx,
        capability_name="workflow.execute.native",  # UNSUPPORTED in registry
    )
    assert decision.decision == PolicyDecisionType.DENY
    assert "UNSUPPORTED" in decision.reason


# 3. Role-Based Access Control (RBAC) Tests
def test_viewer_role_can_read(policy_engine):
    ctx = SecurityContext(actor_id="view-1", role=UserRole.VIEWER, environment=Environment.DEVELOPMENT)
    decision = policy_engine.evaluate(PolicyAction.READ, ctx)
    assert decision.decision == PolicyDecisionType.ALLOW


def test_viewer_role_cannot_modify_or_deploy(policy_engine):
    ctx = SecurityContext(actor_id="view-1", role=UserRole.VIEWER, environment=Environment.DEVELOPMENT)
    for forbidden_action in [PolicyAction.BUILD, PolicyAction.TEST, PolicyAction.MODIFY, PolicyAction.DEPLOY, PolicyAction.DELETE]:
        decision = policy_engine.evaluate(forbidden_action, ctx)
        assert decision.decision == PolicyDecisionType.DENY
        assert "Role VIEWER is unauthorized" in decision.reason


def test_separation_of_duties_engineer_cannot_approve(policy_engine):
    ctx = SecurityContext(actor_id="eng-1", role=UserRole.ENGINEER, environment=Environment.PRODUCTION)
    decision = policy_engine.evaluate(PolicyAction.APPROVE, ctx)
    assert decision.decision == PolicyDecisionType.DENY
    assert "Separation of duties violation" in decision.reason


def test_approver_can_approve(policy_engine):
    ctx = SecurityContext(actor_id="mgr-1", role=UserRole.APPROVER, environment=Environment.PRODUCTION)
    decision = policy_engine.evaluate(PolicyAction.APPROVE, ctx)
    assert decision.decision == PolicyDecisionType.ALLOW


# 4. Production Environment & Approval Gating Tests
def test_production_deployment_unapproved_requires_approval(policy_engine):
    ctx = SecurityContext(actor_id="eng-1", role=UserRole.ENGINEER, environment=Environment.PRODUCTION)
    decision = policy_engine.evaluate(PolicyAction.DEPLOY, ctx, target_environment=Environment.PRODUCTION)
    assert decision.decision == PolicyDecisionType.REQUIRE_APPROVAL
    assert decision.required_approval_type == "PRODUCTION_DEPLOYMENT_GATE"

    with pytest.raises(PolicyViolationError) as exc_info:
        policy_engine.enforce(PolicyAction.DEPLOY, ctx, target_environment=Environment.PRODUCTION)
    assert "REQUIRE_APPROVAL" in str(exc_info.value)


def test_production_deployment_approved_is_allowed(policy_engine):
    ctx = SecurityContext(
        actor_id="eng-1",
        role=UserRole.ENGINEER,
        environment=Environment.PRODUCTION,
        approval_token="appr-token-xyz-12345",
    )
    decision = policy_engine.evaluate(PolicyAction.DEPLOY, ctx, target_environment=Environment.PRODUCTION)
    assert decision.decision == PolicyDecisionType.ALLOW
    assert decision.is_allowed is True


def test_development_deployment_does_not_require_approval(policy_engine):
    ctx = SecurityContext(actor_id="eng-1", role=UserRole.ENGINEER, environment=Environment.DEVELOPMENT)
    decision = policy_engine.evaluate(PolicyAction.DEPLOY, ctx, target_environment=Environment.DEVELOPMENT)
    assert decision.decision == PolicyDecisionType.ALLOW


# 5. Destructive Action Controls
def test_production_delete_by_engineer_is_denied(policy_engine):
    ctx = SecurityContext(actor_id="eng-1", role=UserRole.ENGINEER, environment=Environment.PRODUCTION)
    decision = policy_engine.evaluate(PolicyAction.DELETE, ctx, target_environment=Environment.PRODUCTION)
    assert decision.decision == PolicyDecisionType.DENY
    assert "restricted to ADMINISTRATOR" in decision.reason


def test_production_delete_by_admin_without_approval_requires_approval(policy_engine):
    ctx = SecurityContext(actor_id="admin-1", role=UserRole.ADMINISTRATOR, environment=Environment.PRODUCTION)
    decision = policy_engine.evaluate(PolicyAction.DELETE, ctx, target_environment=Environment.PRODUCTION)
    assert decision.decision == PolicyDecisionType.REQUIRE_APPROVAL
    assert decision.required_approval_type == "HUMAN_GOVERNANCE_GATE"


def test_production_delete_by_admin_with_approval_is_allowed(policy_engine):
    ctx = SecurityContext(
        actor_id="admin-1",
        role=UserRole.ADMINISTRATOR,
        environment=Environment.PRODUCTION,
        approval_token="appr-delete-token-999",
    )
    decision = policy_engine.evaluate(PolicyAction.DELETE, ctx, target_environment=Environment.PRODUCTION)
    assert decision.decision == PolicyDecisionType.ALLOW


# 6. Risk Classifier Tests
def test_risk_classifier_environment_hierarchy():
    # Read is always low
    assert RiskClassifier.classify(PolicyAction.READ, Environment.PRODUCTION) == RiskLevel.LOW

    # Deploy escalation: DEV (LOW) -> TEST (LOW) -> STAGING (MEDIUM) -> PROD (HIGH)
    assert RiskClassifier.classify(PolicyAction.DEPLOY, Environment.DEVELOPMENT) == RiskLevel.LOW
    assert RiskClassifier.classify(PolicyAction.DEPLOY, Environment.STAGING) == RiskLevel.MEDIUM
    assert RiskClassifier.classify(PolicyAction.DEPLOY, Environment.PRODUCTION) == RiskLevel.HIGH

    # Delete escalation
    assert RiskClassifier.classify(PolicyAction.DELETE, Environment.DEVELOPMENT) == RiskLevel.MEDIUM
    assert RiskClassifier.classify(PolicyAction.DELETE, Environment.PRODUCTION) == RiskLevel.CRITICAL

    # Critical override
    assert RiskClassifier.classify(
        PolicyAction.EXECUTE,
        Environment.DEVELOPMENT,
        context={"contains_dangerous_nodes": True}
    ) == RiskLevel.CRITICAL
