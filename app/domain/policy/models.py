"""Domain models for Security Policy, RBAC, Risk, and Authorization Decisions."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID


class UserRole(str, Enum):
    """Permitted conceptual security roles (Security Policy §7)."""
    VIEWER = "VIEWER"
    ENGINEER = "ENGINEER"
    APPROVER = "APPROVER"
    ADMINISTRATOR = "ADMINISTRATOR"
    SYSTEM = "SYSTEM"


class Environment(str, Enum):
    """Target deployment and execution environments (Security Policy §21)."""
    DEVELOPMENT = "DEVELOPMENT"
    TEST = "TEST"
    STAGING = "STAGING"
    PRODUCTION = "PRODUCTION"


class RiskLevel(str, Enum):
    """Operation risk classifications (Security Policy §19)."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class PolicyAction(str, Enum):
    """Granular action types evaluated by the policy engine."""
    READ = "READ"
    BUILD = "BUILD"
    TEST = "TEST"
    EXECUTE = "EXECUTE"
    MODIFY = "MODIFY"
    DEPLOY = "DEPLOY"
    DELETE = "DELETE"
    APPROVE = "APPROVE"
    CONFIGURE = "CONFIGURE"


class PolicyDecisionType(str, Enum):
    """Deterministic policy evaluation outcomes (CODEX_IMPLEMENTATION_PLAN § PHASE 7)."""
    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
    REQUIRE_VERIFICATION = "REQUIRE_VERIFICATION"


@dataclass(frozen=True)
class SecurityContext:
    """Authentication and identity context accompanying an operation request."""
    actor_id: str
    role: UserRole
    environment: Environment = Environment.DEVELOPMENT
    authenticated: bool = True
    approval_token: Optional[str] = None
    approval_id: Optional[UUID] = None
    correlation_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PolicyDecision:
    """Outcome of policy evaluation with actionable explanation."""
    decision: PolicyDecisionType
    action: PolicyAction
    risk_level: RiskLevel
    reason: str
    required_role: Optional[UserRole] = None
    required_approval_type: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_allowed(self) -> bool:
        return self.decision == PolicyDecisionType.ALLOW
