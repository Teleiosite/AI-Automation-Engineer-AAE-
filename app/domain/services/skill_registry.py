"""Skill Registry, Router, and Manifest Verification Service (§15, §26-29, §40 AAE_AGENT_SKILLS.md).

Maintains registered engineering capabilities, performs deterministic dependency resolution,
and routes tasks to appropriate specialist skills while strictly maintaining the authority hierarchy.
"""

from typing import Any, Dict, List, Optional, Set
from uuid import UUID

from app.domain.enums import RiskLevel
from app.domain.errors import DomainValidationError, InvariantViolationError
from app.domain.models.skill import (
    SkillManifest,
    SkillPermissions,
    SkillStatus,
)


class SkillRegistry:
    """Registry maintaining verified specialist engineering skills."""

    def __init__(self) -> None:
        self._skills: Dict[str, SkillManifest] = {}

    def register(self, manifest: SkillManifest) -> None:
        """Register a validated skill manifest."""
        if not isinstance(manifest, SkillManifest):
            raise DomainValidationError("Must provide a valid SkillManifest instance")
        if manifest.name in self._skills:
            raise DomainValidationError(f"Skill '{manifest.name}' is already registered")
        self._skills[manifest.name] = manifest

    def get(self, name: str) -> Optional[SkillManifest]:
        """Fetch skill manifest by kebab-case name."""
        return self._skills.get(name)

    def list_all(self) -> List[SkillManifest]:
        """Return all registered skills ordered alphabetically by name."""
        return sorted(self._skills.values(), key=lambda s: s.name)

    def list_active(self) -> List[SkillManifest]:
        """Return all active skills."""
        return [s for s in self.list_all() if s.status == SkillStatus.ACTIVE]

    def list_by_risk(self, max_risk: RiskLevel) -> List[SkillManifest]:
        """Return skills whose risk level does not exceed max_risk."""
        risk_hierarchy = {
            RiskLevel.LOW: 1,
            RiskLevel.MEDIUM: 2,
            RiskLevel.HIGH: 3,
            RiskLevel.CRITICAL: 4,
        }
        max_val = risk_hierarchy.get(max_risk, 4)
        return [
            s for s in self.list_all()
            if risk_hierarchy.get(s.risk_level, 4) <= max_val
        ]

    def validate_dependencies(self, name: str) -> List[str]:
        """Check if all dependencies for a skill are registered. Returns missing dependency names."""
        manifest = self.get(name)
        if not manifest:
            raise DomainValidationError(f"Skill '{name}' is not registered")

        missing = [dep for dep in manifest.dependencies if dep not in self._skills]
        return missing

    def resolve_dependency_chain(self, root_names: List[str]) -> List[str]:
        """Resolve full dependency tree and return ordered invocation sequence (dependencies first)."""
        visited: Set[str] = set()
        order: List[str] = []

        def visit(n: str, current_path: Set[str]) -> None:
            if n in current_path:
                raise InvariantViolationError(f"Circular skill dependency detected involving '{n}'")
            if n in visited:
                return

            manifest = self.get(n)
            if not manifest:
                raise DomainValidationError(f"Required dependency skill '{n}' is not registered")

            current_path.add(n)
            for dep in manifest.dependencies:
                visit(dep, current_path)
            current_path.remove(n)

            visited.add(n)
            order.append(n)

        for root in root_names:
            visit(root, set())

        return order


class SkillRouter:
    """Deterministic routing mechanism selecting required skills based on task nature and risk."""

    TASK_SKILL_MAP: Dict[str, List[str]] = {
        "architecture": ["automation-architecture"],
        "plan": ["automation-architecture"],
        "build": ["automation-architecture", "n8n-engineering"],
        "validate": ["n8n-workflow-validation", "security"],
        "test": ["testing"],
        "diagnose": ["n8n-engineering", "observability"],
        "repair": ["n8n-engineering", "testing"],
        "api": ["fastapi", "security", "testing"],
        "database": ["postgresql", "security"],
        "agent": ["ai-agent-engineering"],
        "monitor": ["observability"],
    }

    def __init__(self, registry: SkillRegistry) -> None:
        self.registry = registry

    def route_for_task(
        self,
        task_type: str,
        requested_skills: Optional[List[str]] = None,
        context_risk: RiskLevel = RiskLevel.LOW,
    ) -> List[SkillManifest]:
        """Deterministically determine and order the skills required for a task."""
        task_key = task_type.lower().strip()
        selected_names: List[str] = []

        # 1. Base mapped skills
        if task_key in self.TASK_SKILL_MAP:
            selected_names.extend(self.TASK_SKILL_MAP[task_key])

        # 2. Add explicitly requested skills
        if requested_skills:
            for req in requested_skills:
                if req not in selected_names:
                    selected_names.append(req)

        # 3. High/Critical risk contexts always mandate security skill
        if context_risk in (RiskLevel.HIGH, RiskLevel.CRITICAL):
            if "security" not in selected_names:
                selected_names.append("security")

        # 4. Resolve dependency ordering
        ordered_names = self.registry.resolve_dependency_chain(selected_names)

        # 5. Retrieve manifests
        manifests: List[SkillManifest] = []
        for name in ordered_names:
            manifest = self.registry.get(name)
            if manifest and manifest.status == SkillStatus.ACTIVE:
                manifests.append(manifest)

        return manifests


def get_default_skill_registry() -> SkillRegistry:
    """Instantiate and populate registry with the 9 core AAE MVP skills (§15 AAE_AGENT_SKILLS.md)."""
    registry = SkillRegistry()

    # 1. /automation-architecture
    registry.register(
        SkillManifest(
            name="automation-architecture",
            version="1.0.0",
            purpose=["Automation architecture design and pattern formulation"],
            risk_level=RiskLevel.HIGH,
            description="Engineering skill for decomposing automation requests into sound architectural topologies.",
            inputs=["requirement_specification", "environment_capabilities"],
            outputs=["workflow_topology", "architecture_decision"],
            permissions=SkillPermissions(read_workflows=True),
            dependencies=[],
            evidence_required=["approved_specification"],
            escalation=["unsupported_pattern", "ambiguous_boundary"],
        )
    )

    # 2. /security
    registry.register(
        SkillManifest(
            name="security",
            version="1.0.0",
            purpose=["Security analysis, policy validation, credential protection, and risk classification"],
            risk_level=RiskLevel.CRITICAL,
            description="Engineering skill for auditing credentials, expression injection risks, and authorization boundaries.",
            inputs=["workflow_definition", "policy_context"],
            outputs=["security_findings", "risk_classification"],
            permissions=SkillPermissions(read_workflows=True),
            dependencies=[],
            evidence_required=["credential_audit", "expression_scan"],
            escalation=["critical_vulnerability", "hardcoded_secret", "unauthorized_scope"],
        )
    )

    # 3. /n8n-workflow-validation
    registry.register(
        SkillManifest(
            name="n8n-workflow-validation",
            version="1.0.0",
            purpose=["7-layer n8n workflow validation"],
            risk_level=RiskLevel.HIGH,
            description="Engineering skill verifying schema compliance, graph integrity, parameters, and secret leakage.",
            inputs=["workflow_json", "capability_catalog"],
            outputs=["validation_report", "issue_list"],
            permissions=SkillPermissions(read_workflows=True),
            dependencies=["security"],
            evidence_required=["schema_conformance", "graph_acyclicity"],
            escalation=["schema_mismatch", "unverified_capability"],
        )
    )

    # 4. /testing
    registry.register(
        SkillManifest(
            name="testing",
            version="1.0.0",
            purpose=["Test scenario construction, test execution, and technical/semantic assertion evaluation"],
            risk_level=RiskLevel.HIGH,
            description="Engineering skill designing and executing discrete verification tests against workflows.",
            inputs=["workflow_id", "specification", "test_scenarios"],
            outputs=["test_report", "assertion_results"],
            permissions=SkillPermissions(read_workflows=True, execute_workflows="conditional"),
            dependencies=[],
            evidence_required=["test_run_evidence", "assertion_evaluations"],
            escalation=["semantic_failure", "destructive_test_attempt"],
        )
    )

    # 5. /n8n-engineering
    registry.register(
        SkillManifest(
            name="n8n-engineering",
            version="1.0.0",
            purpose=["n8n workflow construction, manipulation, compiler generation, and node configuration"],
            risk_level=RiskLevel.HIGH,
            description="Engineering skill translating plans into canonical n8n JSON structures.",
            inputs=["workflow_plan", "specification", "capability_catalog"],
            outputs=["n8n_workflow_json", "node_manifest"],
            permissions=SkillPermissions(
                read_workflows=True,
                create_workflows=True,
                update_workflows=True,
                execute_workflows="conditional",
                activate_workflows="conditional",
                delete_workflows=False,
                production_deploy=False,
            ),
            dependencies=["automation-architecture", "security", "n8n-workflow-validation", "testing"],
            evidence_required=["provider_capability", "runtime_verification", "workflow_validation"],
            escalation=["unknown_capability", "authorization_failure", "destructive_operation", "production_change"],
        )
    )

    # 6. /ai-agent-engineering
    registry.register(
        SkillManifest(
            name="ai-agent-engineering",
            version="1.0.0",
            purpose=["AI agent design, state machine progression, loop prevention, and prompt isolation"],
            risk_level=RiskLevel.HIGH,
            description="Engineering skill constructing resilient agent prompt strategies and loop controls.",
            inputs=["agent_specification", "task_context"],
            outputs=["agent_topology", "guardrail_spec"],
            permissions=SkillPermissions(read_workflows=True),
            dependencies=[],
            evidence_required=["prompt_isolation", "loop_bounds"],
            escalation=["uncontrolled_loop", "prompt_injection"],
        )
    )

    # 7. /fastapi
    registry.register(
        SkillManifest(
            name="fastapi",
            version="1.0.0",
            purpose=["FastAPI REST endpoints, schema validation, dependency injection, and HTTP routing"],
            risk_level=RiskLevel.HIGH,
            description="Engineering skill designing performant and secure API boundaries.",
            inputs=["api_specification", "route_requirements"],
            outputs=["api_endpoints", "pydantic_schemas"],
            permissions=SkillPermissions(read_workflows=True),
            dependencies=["security", "testing"],
            evidence_required=["openapi_schema", "route_tests"],
            escalation=["auth_bypass", "insecure_cors"],
        )
    )

    # 8. /postgresql
    registry.register(
        SkillManifest(
            name="postgresql",
            version="1.0.0",
            purpose=["Relational schema design, migration management, concurrency control, and index optimization"],
            risk_level=RiskLevel.HIGH,
            description="Engineering skill for ACID transaction boundaries, foreign key integrity, and migrations.",
            inputs=["data_model", "migration_requirements"],
            outputs=["schema_migration", "sql_queries"],
            permissions=SkillPermissions(read_workflows=True),
            dependencies=["security"],
            evidence_required=["migration_test", "transaction_boundary"],
            escalation=["destructive_migration", "missing_index"],
        )
    )

    # 9. /observability
    registry.register(
        SkillManifest(
            name="observability",
            version="1.0.0",
            purpose=["Telemetry ingestion, SLA tracking, latency analysis, and diagnostic escalation"],
            risk_level=RiskLevel.MEDIUM,
            description="Engineering skill monitoring execution health, error rates, and p95 latencies.",
            inputs=["telemetry_records", "sla_thresholds"],
            outputs=["health_report", "alerts"],
            permissions=SkillPermissions(read_workflows=True),
            dependencies=[],
            evidence_required=["metric_samples"],
            escalation=["sla_breach", "critical_failure_burst"],
        )
    )

    return registry
