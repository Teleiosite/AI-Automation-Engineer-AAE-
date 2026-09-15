"""Controlled Repair Engine Service (§16 AAE_AGENT_SPECIFICATION, §36-37 CODEX_IMPLEMENTATION_PLAN).

Transforms structured diagnoses into surgical, validated, version-preserving repair patches
without mutating historical versions or applying unconstrained changes.
"""

import copy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import re
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID, uuid4

from app.domain.enums import FailureCategory, RiskLevel
from app.domain.errors import DomainValidationError, InvariantViolationError
from app.domain.models.repair import RepairAttempt
from app.domain.models.workflow import Workflow, WorkflowVersion
from app.domain.services.audit_service import AuditService
from app.domain.services.diagnosis_engine import StructuredDiagnosis


class PatchType(str, Enum):
    PARAMETER_UPDATE = "PARAMETER_UPDATE"
    RETRY_POLICY = "RETRY_POLICY"
    EXPRESSION_FIX = "EXPRESSION_FIX"
    THROTTLE_ADD = "THROTTLE_ADD"
    ERROR_HANDLER = "ERROR_HANDLER"


@dataclass(frozen=True)
class RepairPatch:
    """Discrete surgical mutation applied to a workflow node."""
    target_node: str
    patch_type: PatchType
    field_path: str
    new_value: Any
    rationale: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_node": self.target_node,
            "patch_type": self.patch_type.value,
            "field_path": self.field_path,
            "new_value": self.new_value,
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class RepairProposal:
    """Structured proposal containing discrete patches addressing an identified failure."""
    diagnosis_id: UUID
    workflow_id: UUID
    target_version_number: int
    patches: List[RepairPatch]
    rationale: str
    risk: RiskLevel = RiskLevel.LOW
    proposal_id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "proposal_id": str(self.proposal_id),
            "diagnosis_id": str(self.diagnosis_id),
            "workflow_id": str(self.workflow_id),
            "target_version_number": self.target_version_number,
            "rationale": self.rationale,
            "risk": self.risk.value,
            "created_at": self.created_at.isoformat(),
            "patches": [p.to_dict() for p in self.patches],
        }


class RepairEngine:
    """Engine synthesizing repair proposals and executing versioned repairs."""

    def __init__(self, audit_service: Optional[AuditService] = None) -> None:
        self.audit_service = audit_service

    def propose_repair(
        self,
        diagnosis: StructuredDiagnosis,
        definition: Dict[str, Any],
    ) -> RepairProposal:
        """Analyze diagnosis and synthesize precise surgical patches."""
        patches: List[RepairPatch] = []
        target_node = diagnosis.failure_node
        nodes = definition.get("nodes", [])

        node_data = next((n for n in nodes if n.get("name") == target_node), None)
        if not node_data and nodes:
            node_data = nodes[-1]
            target_node = node_data.get("name", "Unknown Node")

        # 1. Timeout / Network Failure Repair: Add retryOnFail policy
        if diagnosis.failure_type == FailureCategory.TIMEOUT:
            patches.append(
                RepairPatch(
                    target_node=target_node,
                    patch_type=PatchType.RETRY_POLICY,
                    field_path="retryOnFail",
                    new_value=True,
                    rationale="Enable automatic transient failure retry",
                )
            )
            patches.append(
                RepairPatch(
                    target_node=target_node,
                    patch_type=PatchType.RETRY_POLICY,
                    field_path="maxTries",
                    new_value=3,
                    rationale="Configure retry attempts to 3 with exponential backoff",
                )
            )
            rationale = f"Add resilient retry policy to node '{target_node}' to mitigate network timeouts."

        # 2. Configuration & Expression Error Repair: Fix syntax or unclosed braces
        elif diagnosis.failure_type == FailureCategory.CONFIGURATION_ERROR:
            params = node_data.get("parameters", {}) if node_data else {}
            fixed_field, fixed_val = self._find_and_fix_expression(params)
            if fixed_field:
                patches.append(
                    RepairPatch(
                        target_node=target_node,
                        patch_type=PatchType.EXPRESSION_FIX,
                        field_path=f"parameters.{fixed_field}",
                        new_value=fixed_val,
                        rationale=f"Corrected unclosed or malformed expression in parameter '{fixed_field}'",
                    )
                )
                rationale = f"Corrected malformed parameter expression in node '{target_node}'."
            else:
                patches.append(
                    RepairPatch(
                        target_node=target_node,
                        patch_type=PatchType.PARAMETER_UPDATE,
                        field_path="parameters.options.continueOnFail",
                        new_value=True,
                        rationale="Prevent workflow halt on non-fatal configuration warning",
                    )
                )
                rationale = f"Configured continueOnFail fallback for node '{target_node}'."

        # 3. Rate Limit Repair: Add backoff throttling
        elif diagnosis.failure_type == FailureCategory.RATE_LIMIT:
            patches.append(
                RepairPatch(
                    target_node=target_node,
                    patch_type=PatchType.THROTTLE_ADD,
                    field_path="parameters.options.retryOnRateLimit",
                    new_value=True,
                    rationale="Enable rate limit backoff throttling",
                )
            )
            rationale = f"Enable rate limit backoff handler on node '{target_node}'."

        # 4. Semantic / Logic Error Repair: Adjust output mapping
        elif diagnosis.failure_type == FailureCategory.LOGIC_ERROR:
            patches.append(
                RepairPatch(
                    target_node=target_node,
                    patch_type=PatchType.PARAMETER_UPDATE,
                    field_path="parameters.includeAllFields",
                    new_value=True,
                    rationale="Include all accumulated pipeline fields in node output to satisfy semantic criteria",
                )
            )
            rationale = f"Adjusted data mapping on node '{target_node}' to preserve semantic business fields."

        # 5. Default Fallback Repair
        else:
            patches.append(
                RepairPatch(
                    target_node=target_node,
                    patch_type=PatchType.ERROR_HANDLER,
                    field_path="retryOnFail",
                    new_value=True,
                    rationale="Safely enable retryOnFail fallback",
                )
            )
            rationale = f"Added generic resilience policy to node '{target_node}'."

        return RepairProposal(
            diagnosis_id=diagnosis.id,
            workflow_id=diagnosis.workflow_id,
            target_version_number=diagnosis.workflow_version_number,
            patches=patches,
            rationale=rationale,
            risk=diagnosis.risk,
        )

    def apply_repair(
        self,
        workflow: Workflow,
        proposal: RepairProposal,
        created_by: str = "repairer",
        correlation_id: Optional[str] = None,
    ) -> Tuple[WorkflowVersion, RepairAttempt]:
        """Apply repair patches creating a NEW workflow version (preserving historical versions)."""
        current_version = workflow.get_current_version()
        if not current_version:
            raise InvariantViolationError(f"Workflow {workflow.id} has no versions to repair")

        # Deep copy definition to protect historical version
        patched_definition = copy.deepcopy(current_version.definition)
        nodes = patched_definition.get("nodes", [])

        # Apply each patch surgically
        for patch in proposal.patches:
            target_node = next((n for n in nodes if n.get("name") == patch.target_node), None)
            if not target_node:
                continue

            # Apply field update (supporting dotted field_path)
            parts = patch.field_path.split(".")
            cur = target_node
            for part in parts[:-1]:
                if part not in cur or not isinstance(cur[part], dict):
                    cur[part] = {}
                cur = cur[part]
            cur[parts[-1]] = patch.new_value

        # Create new version in Workflow aggregate (preserving immutable history)
        new_version = workflow.add_version(
            specification_version_id=current_version.specification_version_id,
            definition=patched_definition,
            change_reason=f"Applied repair proposal: {proposal.rationale}",
            created_by=created_by,
        )

        # Record repair attempt
        attempt = RepairAttempt(
            workflow_id=workflow.id,
            target_version_number=new_version.version_number,
            failure_id=proposal.diagnosis_id,
            diagnostic_id=proposal.diagnosis_id,
            proposed_change=proposal.to_dict(),
            risk=proposal.risk,
        )
        attempt.mark_applied()

        # Record audit mutation
        if self.audit_service:
            self.audit_service.record_workflow_mutation(
                mutation_type="repaired",
                workflow_id=str(workflow.id),
                actor=created_by,
                version_number=new_version.version_number,
                before_state={"version_number": current_version.version_number},
                after_state={"version_number": new_version.version_number, "patches": len(proposal.patches)},
                change_reason=f"Repaired from version {current_version.version_number}: {proposal.rationale}",
                correlation_id=correlation_id,
            )

        return new_version, attempt

    def rollback(
        self,
        workflow: Workflow,
        target_version_number: int,
        reason: str = "Repair failed; rollback to known stable version",
        actor: str = "repairer",
        correlation_id: Optional[str] = None,
    ) -> WorkflowVersion:
        """Roll back workflow by creating a new version restoring historical definition."""
        target_version: Optional[WorkflowVersion] = None
        for v in workflow.versions:
            if v.version_number == target_version_number:
                target_version = v
                break

        if not target_version:
            raise InvariantViolationError(f"Target rollback version {target_version_number} does not exist")

        restored_definition = copy.deepcopy(target_version.definition)

        new_version = workflow.add_version(
            specification_version_id=target_version.specification_version_id,
            definition=restored_definition,
            change_reason=f"Rollback to version {target_version_number}: {reason}",
            created_by=actor,
        )

        if self.audit_service:
            self.audit_service.record_workflow_mutation(
                mutation_type="rolled_back",
                workflow_id=str(workflow.id),
                actor=actor,
                version_number=new_version.version_number,
                before_state={"rolled_back_from_version": workflow.current_version_id},
                after_state={"restored_version": target_version_number},
                change_reason=reason,
                correlation_id=correlation_id,
            )

        return new_version

    def _find_and_fix_expression(self, params: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
        """Identify unclosed braces in parameters and return fixed value."""
        for k, v in params.items():
            if isinstance(v, str) and ("{" in v or "}" in v):
                open_count = v.count("{")
                close_count = v.count("}")
                if open_count > close_count:
                    missing = open_count - close_count
                    fixed = v + ("}" * missing)
                    return k, fixed
        return None, None
