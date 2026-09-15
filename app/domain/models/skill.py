"""Domain models for AAE Agent Skills Framework (§4-10 AAE_AGENT_SKILLS.md).

Defines skill identity, manifests, permissions, contracts, and execution records.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import re
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from app.domain.enums import RiskLevel
from app.domain.errors import DomainValidationError


class SkillStatus(str, Enum):
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    EXPERIMENTAL = "experimental"


@dataclass(frozen=True)
class SkillPermissions:
    """Explicit permission boundaries for a specialist engineering skill."""
    read_workflows: bool = True
    create_workflows: bool = False
    update_workflows: bool = False
    execute_workflows: str = "conditional"  # "true", "false", "conditional"
    activate_workflows: str = "conditional"
    delete_workflows: bool = False
    production_deploy: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "read_workflows": self.read_workflows,
            "create_workflows": self.create_workflows,
            "update_workflows": self.update_workflows,
            "execute_workflows": self.execute_workflows,
            "activate_workflows": self.activate_workflows,
            "delete_workflows": self.delete_workflows,
            "production_deploy": self.production_deploy,
        }


_KEBAB_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


@dataclass(frozen=True)
class SkillManifest:
    """Machine-readable contract and manifest for an AAE specialist engineering skill (§40)."""
    name: str
    version: str
    purpose: List[str]
    risk_level: RiskLevel = RiskLevel.MEDIUM
    status: SkillStatus = SkillStatus.ACTIVE
    description: str = ""
    inputs: List[str] = field(default_factory=list)
    outputs: List[str] = field(default_factory=list)
    permissions: SkillPermissions = field(default_factory=SkillPermissions)
    dependencies: List[str] = field(default_factory=list)
    evidence_required: List[str] = field(default_factory=list)
    escalation: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.name or not _KEBAB_PATTERN.match(self.name):
            raise DomainValidationError(
                f"Skill name '{self.name}' must be valid lowercase kebab-case (e.g. 'n8n-engineering')"
            )
        if not self.version or not self.version.strip():
            raise DomainValidationError("Skill version must not be empty")
        if not self.purpose:
            raise DomainValidationError("Skill must define at least one purpose statement")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "status": self.status.value,
            "purpose": list(self.purpose),
            "risk_level": self.risk_level.value,
            "description": self.description,
            "inputs": list(self.inputs),
            "outputs": list(self.outputs),
            "permissions": self.permissions.to_dict(),
            "dependencies": list(self.dependencies),
            "evidence_required": list(self.evidence_required),
            "escalation": list(self.escalation),
        }


@dataclass(frozen=True)
class SkillExecutionResult:
    """Discrete outcome record of an executed specialist skill (§8-10)."""
    skill_name: str
    status: str  # COMPLETED, FAILED, ESCALATED, BLOCKED
    output_data: Dict[str, Any] = field(default_factory=dict)
    evidence: List[str] = field(default_factory=list)
    violations: List[str] = field(default_factory=list)
    escalation_reason: Optional[str] = None
    id: UUID = field(default_factory=uuid4)
    executed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "skill_name": self.skill_name,
            "status": self.status,
            "output_data": self.output_data,
            "evidence": list(self.evidence),
            "violations": list(self.violations),
            "escalation_reason": self.escalation_reason,
            "executed_at": self.executed_at.isoformat(),
        }
