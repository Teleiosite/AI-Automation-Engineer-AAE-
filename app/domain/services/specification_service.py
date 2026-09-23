"""Specification & Human Approval Service (Phase 8).

Converts validated Requirement aggregates into canonical, versioned, tamper-evident
Specifications and enforces formal human approval before allowing workflow construction.
"""

from datetime import datetime, timezone
import re
from typing import Any, Callable, Dict, List, Optional
from uuid import UUID, uuid4

from app.domain.enums import (
    ApprovalDecision,
    ApprovalStatus,
    ConfidenceLevel,
    RequirementType,
    RiskLevel,
    SpecificationStatus,
)
from app.domain.errors import (
    DomainValidationError,
    ImmutableArtifactError,
    InvariantViolationError,
)
from app.domain.models.approval import Approval
from app.domain.models.requirement import Requirement
from app.domain.models.specification import Specification, SpecificationVersion
from app.domain.services.audit_service import AuditService, compute_state_hash


class SpecificationService:
    """Domain service managing Specification lifecycle, immutability, drift detection,
    and the mandatory Human Approval Gate.
    """

    def __init__(self, audit_service: Optional[AuditService] = None) -> None:
        self.audit_service = audit_service

    def create_specification_from_requirement(
        self,
        requirement: Requirement,
        allow_draft_on_ambiguity: bool = False,
        correlation_id: Optional[str] = None,
    ) -> Specification:
        """Construct a new Specification aggregate from a Requirement aggregate."""
        if not allow_draft_on_ambiguity:
            requirement.assert_ready_for_specification()

        structured_content = self._build_canonical_content(requirement)

        spec = Specification(
            project_id=requirement.project_id,
            requirement_id=requirement.id,
        )

        version = spec.add_version(structured_content)
        if requirement.has_ambiguities() or requirement.has_unresolved_conflicts():
            spec.status = SpecificationStatus.CLARIFICATION_REQUIRED

        if self.audit_service:
            self.audit_service.record_workflow_mutation(
                mutation_type="specification.created",
                workflow_id=str(spec.id),
                actor=requirement.created_by,
                version_number=spec.current_version_number,
                before_state=None,
                after_state=structured_content,
                change_reason="Initial specification creation from requirement",
                correlation_id=correlation_id,
            )

        return spec

    def submit_for_review(
        self,
        specification: Specification,
        actor: str = "agent",
        correlation_id: Optional[str] = None,
    ) -> None:
        """Promote a specification from DRAFT to READY_FOR_REVIEW."""
        current_ver = specification.get_current_version()
        if not current_ver:
            raise InvariantViolationError("Specification has no versions to review")

        content = current_ver.structured_content
        if content.get("ambiguities") or content.get("conflicts"):
            raise InvariantViolationError(
                "Cannot submit specification for review while unresolved ambiguities or conflicts remain"
            )

        specification.submit_for_review()

        if self.audit_service:
            self.audit_service.record_workflow_mutation(
                mutation_type="specification.submitted_for_review",
                workflow_id=str(specification.id),
                actor=actor,
                version_number=specification.current_version_number,
                before_state={"status": SpecificationStatus.DRAFT.value},
                after_state={"status": SpecificationStatus.READY_FOR_REVIEW.value},
                change_reason="Specification submitted for human review",
                correlation_id=correlation_id,
            )

    def approve_specification(
        self,
        specification: Specification,
        version_number: int,
        approver: str,
        comments: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> Approval:
        """Formally approve a specification version and issue an authorized Approval token."""
        if not approver or not approver.strip():
            raise DomainValidationError("Approver identity cannot be empty; silence is not approval")

        target_version = specification.get_version(version_number)
        if not target_version:
            raise InvariantViolationError(f"Specification version {version_number} does not exist")

        specification.approve(version_number)

        approval = Approval(
            target_type="specification",
            target_id=specification.id,
            target_version=version_number,
            actor=approver,
            action="construct_workflow",
            environment="development",
            status=ApprovalStatus.ACTIVE,
            decision=ApprovalDecision.APPROVED,
            comments=comments,
        )

        if self.audit_service:
            self.audit_service.record_approval_lifecycle(
                event_name="created",
                approval=approval,
                actor=approver,
                correlation_id=correlation_id,
                notes=comments,
            )

        return approval

    def reject_specification(
        self,
        specification: Specification,
        rejecter: str,
        reason: str,
        correlation_id: Optional[str] = None,
    ) -> None:
        """Formally reject a specification."""
        if not rejecter or not rejecter.strip():
            raise DomainValidationError("Rejecter identity cannot be empty")
        if not reason or not reason.strip():
            raise DomainValidationError("Rejection reason cannot be empty")

        specification.reject(reason)

        if self.audit_service:
            self.audit_service.record_workflow_mutation(
                mutation_type="specification.rejected",
                workflow_id=str(specification.id),
                actor=rejecter,
                version_number=specification.current_version_number,
                before_state={"status": specification.status.value},
                after_state={"status": SpecificationStatus.REJECTED.value, "reason": reason},
                change_reason=reason,
                correlation_id=correlation_id,
            )

    def request_changes(
        self,
        specification: Specification,
        actor: str,
        feedback: str,
        correlation_id: Optional[str] = None,
    ) -> None:
        """Request changes or clarification, returning specification to CLARIFICATION_REQUIRED."""
        if not feedback or not feedback.strip():
            raise DomainValidationError("Feedback cannot be empty when requesting changes")

        specification.request_clarification()

        if self.audit_service:
            self.audit_service.record_workflow_mutation(
                mutation_type="specification.changes_requested",
                workflow_id=str(specification.id),
                actor=actor,
                version_number=specification.current_version_number,
                before_state=None,
                after_state={"feedback": feedback},
                change_reason=feedback,
                correlation_id=correlation_id,
            )

    def create_new_version(
        self,
        specification: Specification,
        updated_requirement: Requirement,
        author: str = "agent",
        correlation_id: Optional[str] = None,
    ) -> SpecificationVersion:
        """Create a new version on an existing specification, preserving immutable history."""
        new_content = self._build_canonical_content(updated_requirement)
        new_version = specification.add_version(new_content)

        if self.audit_service:
            self.audit_service.record_workflow_mutation(
                mutation_type="specification.version_added",
                workflow_id=str(specification.id),
                actor=author,
                version_number=new_version.version_number,
                before_state={"version": new_version.version_number - 1},
                after_state={"version": new_version.version_number, "content": new_content},
                change_reason="New specification version created from updated requirements",
                correlation_id=correlation_id,
            )

        return new_version

    def detect_drift(
        self,
        specification_content: Dict[str, Any],
        proposed_plan: Dict[str, Any],
    ) -> List[str]:
        """Detect drift where a proposed workflow plan diverges from the approved specification."""
        drift_discrepancies: List[str] = []

        # 1. Check data store consistency (preserving casing in discrepancy report)
        spec_stores_lower = {ds.get("name", "").lower() for ds in specification_content.get("data_stores", [])}
        unauthorized_stores = [
            ds for ds in proposed_plan.get("data_stores", [])
            if ds.lower() not in spec_stores_lower
        ]
        if unauthorized_stores:
            drift_discrepancies.append(
                f"Unauthorized data stores in plan: {', '.join(unauthorized_stores)}"
            )

        # 2. Check external service consistency
        spec_services_lower = {es.get("name", "").lower() for es in specification_content.get("external_services", [])}
        unauthorized_services = [
            es for es in proposed_plan.get("external_services", [])
            if es.lower() not in spec_services_lower
        ]
        if unauthorized_services:
            drift_discrepancies.append(
                f"Unauthorized external services in plan: {', '.join(unauthorized_services)}"
            )

        # 3. Check destructive actions
        spec_has_destructive = any(
            act.get("is_destructive", False) for act in specification_content.get("actions", [])
        )
        plan_has_destructive = bool(proposed_plan.get("has_destructive_operations", False))
        if plan_has_destructive and not spec_has_destructive:
            drift_discrepancies.append(
                "Plan introduces destructive operations not authorized by approved specification"
            )

        # 4. Check missing required actions
        spec_actions = [act.get("description", "") for act in specification_content.get("actions", [])]
        plan_actions = proposed_plan.get("planned_actions", [])
        if len(plan_actions) < len(spec_actions):
            drift_discrepancies.append(
                f"Planned actions count ({len(plan_actions)}) is fewer than specified actions ({len(spec_actions)})"
            )

        return drift_discrepancies

    def _build_canonical_content(self, requirement: Requirement) -> Dict[str, Any]:
        """Convert Requirement aggregate into canonical structured specification schema."""
        triggers = [item.description for item in requirement.items if item.type == RequirementType.TRIGGER]
        actions = [
            {
                "description": item.description,
                "confidence": item.confidence.value,
                "risk": item.risk.value,
                "is_destructive": item.risk in (RiskLevel.HIGH, RiskLevel.CRITICAL) and "destruct" in item.description.lower(),
            }
            for item in requirement.items
            if item.type == RequirementType.ACTION
        ]
        inputs = [item.description for item in requirement.items if item.type == RequirementType.INPUT]
        data_stores = [
            {"name": item.description.replace("Data store integration: ", "")}
            for item in requirement.items
            if item.type == RequirementType.DATA_SOURCE
        ]
        external_services = [
            {"name": item.description.replace("External service integration: ", "")}
            for item in requirement.items
            if item.type == RequirementType.EXTERNAL_SERVICE
        ]
        timing = [item.description for item in requirement.items if item.type == RequirementType.TIMING]
        security_reqs = [item.description for item in requirement.items if item.type == RequirementType.SECURITY_REQUIREMENT]
        success_criteria = [item.description for item in requirement.items if item.type == RequirementType.SUCCESS_CRITERIA]
        semantic_requirements = [
            {
                "type": item.type.value,
                "description": item.description,
                "confidence": item.confidence.value,
                "risk": item.risk.value,
                # Contracts contain only values explicitly present in the source
                # request. Missing values remain empty and cannot be invented by
                # the planner.
                "contract": self._build_semantic_contract(item.type, requirement.original_request),
            }
            for item in requirement.items
            if item.type in {
                RequirementType.STATE_MACHINE, RequirementType.APPROVAL_POLICY,
                RequirementType.DOCUMENT_EXTRACTION, RequirementType.EVALUATION_CRITERIA,
                RequirementType.AUDIT_REQUIREMENT, RequirementType.SLA_POLICY,
                RequirementType.CONVERSATIONAL_INTERFACE,
            }
        ]
        outputs = ["validated trigger payload"]
        if data_stores:
            outputs.append("database record")
        if external_services:
            outputs.append("outbound notification")
        if any(item["type"] == RequirementType.APPROVAL_POLICY.value for item in semantic_requirements):
            outputs.append("recorded human approval")
        semantic_outputs = {
            RequirementType.STATE_MACHINE.value: "validated lifecycle transition",
            RequirementType.DOCUMENT_EXTRACTION.value: "extracted document fields",
            RequirementType.EVALUATION_CRITERIA.value: "completed weighted evaluation",
            RequirementType.AUDIT_REQUIREMENT.value: "appended audit ledger entry",
            RequirementType.SLA_POLICY.value: "scheduled SLA monitoring",
            RequirementType.CONVERSATIONAL_INTERFACE.value: "grounded query response",
        }
        outputs.extend(semantic_outputs[item["type"]] for item in semantic_requirements if item["type"] in semantic_outputs)
        business_obj = next(
            (item.description for item in requirement.items if item.type == RequirementType.BUSINESS_OBJECTIVE),
            "Automate business process",
        )

        content: Dict[str, Any] = {
            "source_request": {
                "requirement_id": str(requirement.id),
                "project_id": str(requirement.project_id),
                "text": requirement.original_request,
            },
            "business_objective": business_obj,
            "trigger": triggers[0] if triggers else "Unspecified",
            "inputs": inputs,
            "actions": actions,
            "data_stores": data_stores,
            "external_services": external_services,
            "timing": timing,
            "security_requirements": security_reqs,
            "success_criteria": success_criteria,
            "outputs": outputs,
            "semantic_requirements": semantic_requirements,
            "assumptions": list(requirement.assumptions),
            "ambiguities": list(requirement.ambiguities),
            "conflicts": list(requirement.conflicts),
            "risk_level": requirement.overall_risk().value,
        }

        content["content_hash"] = compute_state_hash(content)
        return content

    def _build_semantic_contract(self, requirement_type: RequirementType, source: str) -> Dict[str, Any]:
        """Create a typed contract from explicit source values without guessing.

        Contracts are intentionally data-only so they can be reviewed and hashed
        in the approved specification before the planner uses them.
        """
        text = source.lower()
        if requirement_type == RequirementType.STATE_MACHINE:
            states_match = re.search(r"(?:states?|lifecycle)\s*:\s*([^.;]+)", source, re.IGNORECASE)
            transition_matches = re.findall(r"([A-Za-z][\w -]+)\s*->\s*([A-Za-z][\w -]+)", source)
            states = [value.strip() for value in states_match.group(1).split(",")] if states_match else []
            return {"states": states, "transitions": [{"from": a.strip(), "to": b.strip()} for a, b in transition_matches], "fail_closed": True}
        if requirement_type == RequirementType.APPROVAL_POLICY:
            tiers = [{"threshold": amount.replace(",", ""), "role": role.strip()} for amount, role in re.findall(r"(\$[\d,]+)\s*(?:or below|and above|\+)?\s*[:=-]\s*([A-Za-z][A-Za-z _-]+)", source)]
            return {"tiers": tiers, "reapproval_on_material_change": "re-approval" in text or "reapproval" in text, "fail_closed": True}
        if requirement_type == RequirementType.DOCUMENT_EXTRACTION:
            formats = [name for name in ("pdf", "excel", "spreadsheet", "email") if name in text]
            fields_match = re.search(r"(?:extract(?:ion)?\s+fields?|fields?)\s*:\s*([^.;]+)", source, re.IGNORECASE)
            fields = [value.strip() for value in fields_match.group(1).split(",")] if fields_match else []
            return {"formats": formats, "required_fields": fields, "on_missing": "clarify" if "clarif" in text else None, "fail_closed": True}
        if requirement_type == RequirementType.EVALUATION_CRITERIA:
            weights = [{"criterion": criterion.lower(), "weight": int(weight)} for criterion, weight in re.findall(r"([A-Za-z][A-Za-z _-]+?)\s*(?:=|:|\()\s*(\d{1,3})%", source)]
            return {"weights": weights, "requires_rationale": "rationale" in text or "reason" in text, "fail_closed": True}
        if requirement_type == RequirementType.AUDIT_REQUIREMENT:
            return {"hash_chain": "cryptographic" in text or "hash" in text, "append_only": "immutable" in text or "append-only" in text, "fail_closed": True}
        if requirement_type == RequirementType.SLA_POLICY:
            deadline = re.search(r"(\d+)\s*(minutes?|hours?|days?)", text)
            return {"deadline": {"value": int(deadline.group(1)), "unit": deadline.group(2)} if deadline else None, "escalation_recipient": "manager" if "manager" in text else None, "fail_closed": True}
        if requirement_type == RequirementType.CONVERSATIONAL_INTERFACE:
            return {"grounding_source": "workflow records" if "record" in text else None, "fail_closed": True}
        return {"fail_closed": True}
