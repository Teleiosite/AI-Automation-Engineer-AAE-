"""Deterministic Risk Classifier (Security Policy §19-21)."""

from typing import Any, Dict, Optional

from app.domain.policy.models import Environment, PolicyAction, RiskLevel


class RiskClassifier:
    """Classifies operational risk deterministically based on action, environment, and impact."""

    @staticmethod
    def classify(
        action: PolicyAction,
        environment: Environment,
        resource_type: str = "workflow",
        context: Optional[Dict[str, Any]] = None,
    ) -> RiskLevel:
        """
        Evaluate and return the deterministic RiskLevel.
        Rules:
        1. Critical overrides (dangerous commands, bulk destruction).
        2. Production destructive actions -> CRITICAL.
        3. Production mutations / deployments -> HIGH.
        4. Staging mutations -> MEDIUM.
        5. Read actions -> LOW across all environments.
        6. Dev/Test non-destructive actions -> LOW or MEDIUM.
        """
        ctx = context or {}

        # Check for critical overrides in context or parameters
        if ctx.get("is_bulk_operation") or ctx.get("mass_delete"):
            return RiskLevel.CRITICAL

        dangerous_nodes = ctx.get("contains_dangerous_nodes", False)
        if dangerous_nodes:
            return RiskLevel.CRITICAL

        # READ operations carry minimal risk
        if action == PolicyAction.READ:
            return RiskLevel.LOW

        # APPROVE actions carry medium governance risk
        if action == PolicyAction.APPROVE:
            return RiskLevel.HIGH if environment == Environment.PRODUCTION else RiskLevel.MEDIUM

        # CONFIGURE actions (security settings, credentials)
        if action == PolicyAction.CONFIGURE:
            return RiskLevel.CRITICAL if environment == Environment.PRODUCTION else RiskLevel.HIGH

        # Destructive actions (DELETE)
        if action == PolicyAction.DELETE:
            if environment == Environment.PRODUCTION:
                return RiskLevel.CRITICAL
            elif environment == Environment.STAGING:
                return RiskLevel.HIGH
            return RiskLevel.MEDIUM

        # Production operations
        if environment == Environment.PRODUCTION:
            if action in (PolicyAction.DEPLOY, PolicyAction.MODIFY):
                return RiskLevel.HIGH
            if action == PolicyAction.EXECUTE:
                return RiskLevel.HIGH
            return RiskLevel.MEDIUM

        # Staging operations
        if environment == Environment.STAGING:
            if action in (PolicyAction.DEPLOY, PolicyAction.MODIFY):
                return RiskLevel.MEDIUM
            return RiskLevel.LOW

        # Test operations
        if environment == Environment.TEST:
            if action in (PolicyAction.DEPLOY, PolicyAction.MODIFY):
                return RiskLevel.LOW
            return RiskLevel.LOW

        # Development operations
        return RiskLevel.LOW
