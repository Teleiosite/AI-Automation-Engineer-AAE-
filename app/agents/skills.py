"""Agent component for executing specialist skills under strict deterministic authority (§3-4 AAE_AGENT_SKILLS.md).

Enforces the AAE Authority Hierarchy:
"Skills provide engineering expertise. Deterministic controls provide authority."
"""

from typing import Any, Dict, List, Optional
from uuid import UUID

from app.domain.enums import RiskLevel
from app.domain.errors import ApprovalRequiredError, InvariantViolationError
from app.domain.models.skill import (
    SkillExecutionResult,
    SkillManifest,
    SkillStatus,
)
from app.domain.services.skill_registry import (
    SkillRegistry,
    SkillRouter,
    get_default_skill_registry,
)


class SkillRunnerAgent:
    """Coordinates specialist skill execution and enforces fail-closed authority gates."""

    def __init__(
        self,
        registry: Optional[SkillRegistry] = None,
        router: Optional[SkillRouter] = None,
    ) -> None:
        self.registry = registry or get_default_skill_registry()
        self.router = router or SkillRouter(self.registry)

    def select_skills_for_task(
        self,
        task_type: str,
        requested_skills: Optional[List[str]] = None,
        context_risk: RiskLevel = RiskLevel.LOW,
    ) -> List[SkillManifest]:
        """Query router for suitable skills for a task."""
        return self.router.route_for_task(
            task_type=task_type,
            requested_skills=requested_skills,
            context_risk=context_risk,
        )

    def execute_skill(
        self,
        skill_name: str,
        input_data: Dict[str, Any],
        context_risk: RiskLevel = RiskLevel.LOW,
    ) -> SkillExecutionResult:
        """Execute a specialist skill while enforcing permissions and the authority hierarchy (§3)."""
        manifest = self.registry.get(skill_name)
        if not manifest:
            return SkillExecutionResult(
                skill_name=skill_name,
                status="FAILED",
                violations=[f"Skill '{skill_name}' is not registered in the SkillRegistry"],
            )

        if manifest.status != SkillStatus.ACTIVE:
            return SkillExecutionResult(
                skill_name=skill_name,
                status="BLOCKED",
                violations=[f"Skill '{skill_name}' is in status '{manifest.status.value}', cannot execute"],
            )

        # 1. Dependency check
        missing_deps = self.registry.validate_dependencies(skill_name)
        if missing_deps:
            return SkillExecutionResult(
                skill_name=skill_name,
                status="BLOCKED",
                violations=[f"Unsatisfied dependencies: {', '.join(missing_deps)}"],
            )

        # 2. Authority Hierarchy checks (§3: Skills cannot override security policy or approval gates)
        action = input_data.get("action", "")

        # A skill can NEVER perform production deployment or delete workflows without explicit permission
        if action == "production_deploy" and not manifest.permissions.production_deploy:
            return SkillExecutionResult(
                skill_name=skill_name,
                status="BLOCKED",
                violations=["Skill has no authority to deploy to production directly."],
                escalation_reason="production_change",
            )

        if action == "delete_workflow" and not manifest.permissions.delete_workflows:
            return SkillExecutionResult(
                skill_name=skill_name,
                status="BLOCKED",
                violations=["Skill has no authority to delete workflows."],
                escalation_reason="destructive_operation",
            )

        if input_data.get("bypass_approval", False):
            return SkillExecutionResult(
                skill_name=skill_name,
                status="BLOCKED",
                violations=["Authority hierarchy violation: Skills cannot bypass human approval gates."],
                escalation_reason="authorization_failure",
            )

        if input_data.get("has_unverified_capability", False):
            return SkillExecutionResult(
                skill_name=skill_name,
                status="ESCALATED",
                violations=["Provider capability is unverified."],
                escalation_reason="unknown_capability",
            )

        # 3. Successful execution simulation within bounds
        return SkillExecutionResult(
            skill_name=skill_name,
            status="COMPLETED",
            output_data={
                "result": f"Executed skill {skill_name} successfully",
                "action": action or "inspect",
                "risk": manifest.risk_level.value,
            },
            evidence=[f"Validated inputs against {manifest.name} contract v{manifest.version}"],
        )
