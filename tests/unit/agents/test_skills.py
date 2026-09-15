"""Unit tests for AAE Skills Framework (Phase 19 / §15, §26-29, §40 AAE_AGENT_SKILLS.md)."""

import ast
from pathlib import Path
import pytest

from app.agents.skills import SkillRunnerAgent
from app.domain.enums import RiskLevel
from app.domain.errors import DomainValidationError, InvariantViolationError
from app.domain.models.skill import (
    SkillExecutionResult,
    SkillManifest,
    SkillPermissions,
    SkillStatus,
)
from app.domain.services.skill_registry import (
    SkillRegistry,
    SkillRouter,
    get_default_skill_registry,
)


def test_skills_domain_isolation():
    """Verify skill domain model and service contain zero framework imports."""
    paths = [
        Path("app/domain/models/skill.py"),
        Path("app/domain/services/skill_registry.py"),
    ]
    forbidden = {"fastapi", "sqlalchemy", "pydantic", "httpx", "n8n"}

    for p in paths:
        assert p.exists(), f"File {p} does not exist"
        tree = ast.parse(p.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for name in node.names:
                    root_pkg = name.name.split(".")[0]
                    assert root_pkg not in forbidden, f"Forbidden import in {p}: {name.name}"
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    root_pkg = node.module.split(".")[0]
                    assert root_pkg not in forbidden, f"Forbidden from-import in {p}: {node.module}"


def test_skill_manifest_validation():
    # Valid kebab-case manifest
    manifest = SkillManifest(
        name="custom-tooling",
        version="1.0.0",
        purpose=["Provide specialized tool integrations"],
    )
    assert manifest.name == "custom-tooling"
    assert manifest.version == "1.0.0"
    assert manifest.status == SkillStatus.ACTIVE

    # Invalid name (camelCase or uppercase or spaces)
    with pytest.raises(DomainValidationError):
        SkillManifest(
            name="CustomTooling",
            version="1.0.0",
            purpose=["Test"],
        )

    # Missing purpose
    with pytest.raises(DomainValidationError):
        SkillManifest(
            name="empty-purpose",
            version="1.0.0",
            purpose=[],
        )


def test_default_skill_registry_contents():
    registry = get_default_skill_registry()
    all_skills = registry.list_all()

    # Must contain exactly the 9 MVP core skills (§15)
    assert len(all_skills) == 9
    skill_names = {s.name for s in all_skills}
    expected_skills = {
        "n8n-engineering",
        "automation-architecture",
        "n8n-workflow-validation",
        "ai-agent-engineering",
        "security",
        "testing",
        "fastapi",
        "postgresql",
        "observability",
    }
    assert skill_names == expected_skills


def test_dependency_chain_resolution():
    registry = SkillRegistry()
    registry.register(
        SkillManifest(
            name="base-skill",
            version="1.0.0",
            purpose=["Base capability"],
            dependencies=[],
        )
    )
    registry.register(
        SkillManifest(
            name="mid-skill",
            version="1.0.0",
            purpose=["Mid capability"],
            dependencies=["base-skill"],
        )
    )
    registry.register(
        SkillManifest(
            name="top-skill",
            version="1.0.0",
            purpose=["Top capability"],
            dependencies=["mid-skill"],
        )
    )

    order = registry.resolve_dependency_chain(["top-skill"])
    assert order == ["base-skill", "mid-skill", "top-skill"]


def test_circular_dependency_detected():
    registry = SkillRegistry()
    registry.register(
        SkillManifest(
            name="skill-a",
            version="1.0.0",
            purpose=["A"],
            dependencies=["skill-b"],
        )
    )
    registry.register(
        SkillManifest(
            name="skill-b",
            version="1.0.0",
            purpose=["B"],
            dependencies=["skill-a"],
        )
    )

    with pytest.raises(InvariantViolationError, match="Circular skill dependency"):
        registry.resolve_dependency_chain(["skill-a"])


def test_skill_router_task_mapping_and_risk_elevation():
    registry = get_default_skill_registry()
    router = SkillRouter(registry)

    # Build task resolves dependencies in correct order: architecture -> security -> validation -> testing -> engineering
    build_skills = router.route_for_task("build")
    build_names = [s.name for s in build_skills]
    assert "automation-architecture" in build_names
    assert "n8n-engineering" in build_names
    # Dependency order guarantee
    assert build_names.index("automation-architecture") < build_names.index("n8n-engineering")

    # Low risk task without security
    test_skills = router.route_for_task("test", context_risk=RiskLevel.LOW)
    test_names = [s.name for s in test_skills]
    assert "testing" in test_names
    assert "security" not in test_names

    # Critical risk elevation forces security skill
    crit_skills = router.route_for_task("test", context_risk=RiskLevel.CRITICAL)
    crit_names = [s.name for s in crit_skills]
    assert "security" in crit_names
    assert "testing" in crit_names


def test_skill_runner_agent_authority_hierarchy():
    agent = SkillRunnerAgent()

    # 1. Normal inspection action succeeds
    res = agent.execute_skill("n8n-engineering", {"action": "inspect"})
    assert res.status == "COMPLETED"
    assert len(res.violations) == 0

    # 2. Skill cannot bypass human approval gate (§3: Authority Hierarchy)
    res_bypass = agent.execute_skill("n8n-engineering", {"action": "deploy", "bypass_approval": True})
    assert res_bypass.status == "BLOCKED"
    assert "cannot bypass human approval" in res_bypass.violations[0].lower()
    assert res_bypass.escalation_reason == "authorization_failure"

    # 3. Direct production deploy from skill is forbidden without explicit authorization
    res_prod = agent.execute_skill("n8n-engineering", {"action": "production_deploy"})
    assert res_prod.status == "BLOCKED"
    assert "no authority to deploy to production directly" in res_prod.violations[0]

    # 4. Unverified capability triggers escalation
    res_esc = agent.execute_skill("n8n-engineering", {"has_unverified_capability": True})
    assert res_esc.status == "ESCALATED"
    assert res_esc.escalation_reason == "unknown_capability"
