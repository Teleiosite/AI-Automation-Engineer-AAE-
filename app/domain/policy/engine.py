"""Deterministic Security Policy Engine (Security Policy §4-25, CODEX_IMPLEMENTATION_PLAN § PHASE 7)."""

from typing import Any, Dict, Optional

from app.domain.capabilities.models import CapabilityDecision, CapabilityRegistry, CapabilityStatus
from app.domain.errors import DomainError
from app.domain.policy.classifier import RiskClassifier
from app.domain.policy.models import (
    Environment,
    PolicyAction,
    PolicyDecision,
    PolicyDecisionType,
    RiskLevel,
    SecurityContext,
    UserRole,
)


class PolicyViolationError(DomainError):
    """Raised when an operation violates security policy rules."""
    pass


class PolicyEngine:
    """
    Deterministic policy engine enforcing:
    - Authentication verification
    - Role-Based Access Control (RBAC)
    - Separation of duties (Engineers cannot approve their own deployments)
    - Production environment segregation
    - Destructive action gating
    - Capability status gating (Unknown -> REQUIRE_VERIFICATION, Unsupported -> DENY)
    - Human approval requirements for High/Critical risk actions
    """

    def __init__(self, capability_registry: Optional[CapabilityRegistry] = None) -> None:
        self.capability_registry = capability_registry

    def evaluate(
        self,
        action: PolicyAction,
        security_context: SecurityContext,
        target_environment: Optional[Environment] = None,
        capability_name: Optional[str] = None,
        resource_type: str = "workflow",
        context: Optional[Dict[str, Any]] = None,
    ) -> PolicyDecision:
        """
        Deterministically evaluate a requested action against security policy.
        Returns PolicyDecision with ALLOW, DENY, REQUIRE_APPROVAL, or REQUIRE_VERIFICATION.
        """
        env = target_environment or security_context.environment
        risk = RiskClassifier.classify(
            action=action,
            environment=env,
            resource_type=resource_type,
            context=context,
        )

        # 1. Authentication Check (Fail closed on unauthenticated actor)
        if not security_context.authenticated or not security_context.actor_id:
            return PolicyDecision(
                decision=PolicyDecisionType.DENY,
                action=action,
                risk_level=risk,
                reason="Actor is not authenticated. All protected operations require authentication.",
            )

        # 2. Capability Integration Check
        if capability_name and self.capability_registry:
            cap_decision = self.capability_registry.evaluate(capability_name)
            if cap_decision.status == CapabilityStatus.UNKNOWN:
                return PolicyDecision(
                    decision=PolicyDecisionType.REQUIRE_VERIFICATION,
                    action=action,
                    risk_level=risk,
                    reason=f"Operation capability '{capability_name}' has status UNKNOWN; empirical verification required.",
                )
            if cap_decision.status == CapabilityStatus.UNSUPPORTED:
                return PolicyDecision(
                    decision=PolicyDecisionType.DENY,
                    action=action,
                    risk_level=risk,
                    reason=f"Operation capability '{capability_name}' is UNSUPPORTED by the provider.",
                )
            if cap_decision.status == CapabilityStatus.KNOWN_LIMITATION:
                return PolicyDecision(
                    decision=PolicyDecisionType.DENY,
                    action=action,
                    risk_level=risk,
                    reason=f"Operation capability '{capability_name}' is a KNOWN_LIMITATION.",
                )

        # 3. Role-Based Access Control (RBAC) & Separation of Duties
        role = security_context.role

        # VIEWER can only read
        if role == UserRole.VIEWER and action != PolicyAction.READ:
            return PolicyDecision(
                decision=PolicyDecisionType.DENY,
                action=action,
                risk_level=risk,
                reason=f"Role VIEWER is unauthorized to perform action '{action.value}'. Only READ is permitted.",
                required_role=UserRole.ENGINEER,
            )

        # Separation of Duties: ENGINEER cannot APPROVE
        if role == UserRole.ENGINEER and action == PolicyAction.APPROVE:
            return PolicyDecision(
                decision=PolicyDecisionType.DENY,
                action=action,
                risk_level=risk,
                reason="Separation of duties violation: ENGINEER role cannot approve deployments or changes.",
                required_role=UserRole.APPROVER,
            )

        # Only ADMINISTRATOR can CONFIGURE system security / credentials
        if action == PolicyAction.CONFIGURE and role not in (UserRole.ADMINISTRATOR, UserRole.SYSTEM):
            return PolicyDecision(
                decision=PolicyDecisionType.DENY,
                action=action,
                risk_level=risk,
                reason=f"Action CONFIGURE requires ADMINISTRATOR role. Current role is '{role.value}'.",
                required_role=UserRole.ADMINISTRATOR,
            )

        # 4. Destructive Action & Production Approval Controls
        if action == PolicyAction.DELETE:
            # Delete in production requires explicit admin authorization AND approval
            if env == Environment.PRODUCTION:
                if role not in (UserRole.ADMINISTRATOR, UserRole.SYSTEM):
                    return PolicyDecision(
                        decision=PolicyDecisionType.DENY,
                        action=action,
                        risk_level=risk,
                        reason="Destructive deletion in PRODUCTION is restricted to ADMINISTRATOR.",
                        required_role=UserRole.ADMINISTRATOR,
                    )
                if not security_context.approval_token:
                    return PolicyDecision(
                        decision=PolicyDecisionType.REQUIRE_APPROVAL,
                        action=action,
                        risk_level=risk,
                        reason="Destructive deletion in PRODUCTION requires explicit human approval token.",
                        required_approval_type="HUMAN_GOVERNANCE_GATE",
                    )

        # 5. Production Deployment / Modification Approval Gating
        if env == Environment.PRODUCTION and action in (PolicyAction.DEPLOY, PolicyAction.MODIFY):
            if not security_context.approval_token:
                return PolicyDecision(
                    decision=PolicyDecisionType.REQUIRE_APPROVAL,
                    action=action,
                    risk_level=risk,
                    reason="Material deployment or modification in PRODUCTION requires explicit approval token.",
                    required_approval_type="PRODUCTION_DEPLOYMENT_GATE",
                )

        # 6. Critical Risk Approval Gating
        if risk == RiskLevel.CRITICAL and not security_context.approval_token:
            return PolicyDecision(
                decision=PolicyDecisionType.REQUIRE_APPROVAL,
                action=action,
                risk_level=risk,
                reason="Operation classified as CRITICAL risk requires an explicit approval token.",
                required_approval_type="CRITICAL_RISK_GATE",
            )

        # 7. Approved or Safe Operation Permitted
        approval_note = " (Approved via token)" if security_context.approval_token else ""
        return PolicyDecision(
            decision=PolicyDecisionType.ALLOW,
            action=action,
            risk_level=risk,
            reason=f"Action '{action.value}' authorized for role '{role.value}' in environment '{env.value}'{approval_note}.",
        )

    def enforce(
        self,
        action: PolicyAction,
        security_context: SecurityContext,
        target_environment: Optional[Environment] = None,
        capability_name: Optional[str] = None,
        resource_type: str = "workflow",
        context: Optional[Dict[str, Any]] = None,
    ) -> PolicyDecision:
        """
        Evaluate policy and raise PolicyViolationError if decision is not ALLOW.
        """
        decision = self.evaluate(
            action=action,
            security_context=security_context,
            target_environment=target_environment,
            capability_name=capability_name,
            resource_type=resource_type,
            context=context,
        )
        if decision.decision != PolicyDecisionType.ALLOW:
            raise PolicyViolationError(
                f"Security Policy Violation [{decision.decision.value}]: {decision.reason}"
            )
        return decision
