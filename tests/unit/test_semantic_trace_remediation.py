"""Regression tests for non-vacuous semantic requirement handling."""
from uuid import uuid4

import pytest

from app.domain.enums import ConfidenceLevel, RequirementType, RiskLevel
from app.domain.models.requirement import Requirement, RequirementItem
from app.domain.services.requirement_translator import RequirementTranslator
from app.domain.services.specification_service import SpecificationService
from app.domain.services.workflow_builder import WorkflowBuilder
from app.domain.services.workflow_planner import WorkflowPlanner
from app.domain.services.workflow_test_engine import WorkflowTestEngine
from app.domain.services.workflow_validator import WorkflowValidator


def _approved_procurement_spec():
    requirement = Requirement(project_id=uuid4(), original_request="Procurement request submitted by internal portal. $5000: Manager approval.")
    requirement.add_item(RequirementItem(RequirementType.TRIGGER, "Trigger on: Webhook event", ConfidenceLevel.EXPLICIT))
    requirement.add_item(RequirementItem(RequirementType.ACTION, "Persist incoming record to data store", ConfidenceLevel.EXPLICIT))
    requirement.add_item(RequirementItem(RequirementType.DATA_SOURCE, "Data store integration: PostgreSQL", ConfidenceLevel.EXPLICIT))
    requirement.add_item(RequirementItem(RequirementType.APPROVAL_POLICY, "Human approval policy with scope", ConfidenceLevel.EXPLICIT, RiskLevel.HIGH))
    service = SpecificationService()
    specification = service.create_specification_from_requirement(requirement)
    service.submit_for_review(specification, actor="reviewer")
    service.approve_specification(specification, 1, "reviewer")
    return specification


def test_procurement_semantics_are_preserved_and_ambiguities_are_not_silenced():
    result = RequirementTranslator().translate(
        uuid4(),
        "Build an AI procurement employee that parses PDF quotations, compares suppliers, "
        "uses a lifecycle state machine, and requires spend approval.",
    )

    types = {item.type for item in result.requirement.items}
    assert {RequirementType.DOCUMENT_EXTRACTION, RequirementType.EVALUATION_CRITERIA,
            RequirementType.STATE_MACHINE, RequirementType.APPROVAL_POLICY} <= types
    assert result.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)
    assert result.is_clarification_required
    assert result.clarification_questions


def test_approval_policy_generates_gate_and_nonvacuous_output_contract():
    specification = _approved_procurement_spec()
    content = specification.get_current_version().structured_content
    assert "recorded human approval" in content["outputs"]
    assert content["semantic_requirements"]

    plan = WorkflowPlanner().create_plan(specification)
    assert any(node.node_type == "n8n-nodes-base.wait" for node in plan.nodes)

    definition = WorkflowBuilder().build_workflow_definition(plan)
    assert WorkflowValidator().validate(definition, specification=specification, plan=plan).is_valid
    scenarios = WorkflowTestEngine().generate_scenarios_from_specification(specification)
    assert scenarios[0].expected_outputs


def test_test_engine_rejects_missing_output_contract():
    from app.domain.models.specification import Specification
    specification = Specification(project_id=uuid4(), requirement_id=uuid4())
    specification.add_version({"inputs": [], "outputs": [], "success_criteria": []})
    with pytest.raises(ValueError, match="no verifiable output contract"):
        WorkflowTestEngine().generate_scenarios_from_specification(specification)


def test_semantic_contracts_compile_to_dedicated_and_validated_subgraphs():
    requirement = Requirement(
        project_id=uuid4(),
        original_request=(
            "states: requested, approved; requested -> approved. "
            "$5000: Manager approval. Extract fields: supplier, price from PDF. "
            "price: 60%, quality: 40%. Use cryptographic immutable audit ledger. "
            "Escalate to manager within 2 hours. Answer conversational queries from records."
        ),
    )
    requirement.add_item(RequirementItem(RequirementType.TRIGGER, "Trigger on: Webhook event", ConfidenceLevel.EXPLICIT))
    for item_type in (
        RequirementType.STATE_MACHINE,
        RequirementType.DOCUMENT_EXTRACTION,
        RequirementType.EVALUATION_CRITERIA,
        RequirementType.AUDIT_REQUIREMENT,
        RequirementType.SLA_POLICY,
        RequirementType.CONVERSATIONAL_INTERFACE,
    ):
        requirement.add_item(RequirementItem(item_type, f"{item_type.value} contract", ConfidenceLevel.EXPLICIT))

    service = SpecificationService()
    specification = service.create_specification_from_requirement(requirement)
    service.submit_for_review(specification, actor="reviewer")
    service.approve_specification(specification, 1, "reviewer")
    plan = WorkflowPlanner().create_plan(specification)
    names = {node.name for node in plan.nodes}
    assert {
        "Validate Lifecycle Transition", "Extract Structured Document Fields",
        "Evaluate Decision Matrix", "Append Immutable Audit Ledger",
        "Monitor SLA Deadline", "Return Grounded Query Result",
    } <= names

    definition = WorkflowBuilder().build_workflow_definition(plan)
    assert WorkflowValidator().validate(definition, specification=specification, plan=plan).is_valid
    definition["nodes"] = [node for node in definition["nodes"] if node["name"] != "Evaluate Decision Matrix"]
    report = WorkflowValidator().validate(definition, specification=specification)
    assert any(issue.rule_id == "SEM-009" for issue in report.issues)


def test_incomplete_state_machine_contract_requires_clarification():
    result = RequirementTranslator().translate(uuid4(), "Build a procurement lifecycle state machine.")
    assert result.is_clarification_required
    assert any("Lifecycle contract incomplete" in question for question in result.clarification_questions)
