"""Unit tests for WorkflowPlanner, capability verification, and topology planning (Phase 10)."""

from uuid import uuid4
import pytest

from app.domain.capabilities.models import CapabilityRegistry, get_default_n8n_registry
from app.domain.capabilities.service import CapabilityEnforcementService, CapabilityEnforcementError
from app.domain.enums import ConfidenceLevel, RequirementType, RiskLevel, SpecificationStatus
from app.domain.errors import InvariantViolationError
from app.domain.models.requirement import Requirement, RequirementItem
from app.domain.models.specification import Specification
from app.domain.services.specification_service import SpecificationService
from app.domain.services.workflow_planner import WorkflowPlanner, WorkflowPlan
from app.agents.planner import Planner


@pytest.fixture
def capability_service() -> CapabilityEnforcementService:
    registry = get_default_n8n_registry()
    return CapabilityEnforcementService(registry)


@pytest.fixture
def planner(capability_service) -> WorkflowPlanner:
    return WorkflowPlanner(capability_service=capability_service)


@pytest.fixture
def approved_specification() -> Specification:
    req = Requirement(
        project_id=uuid4(),
        original_request="Whenever contact form is submitted, save to PostgreSQL and send WhatsApp message.",
    )
    req.add_item(RequirementItem(type=RequirementType.TRIGGER, description="Trigger on: Website form submission", confidence=ConfidenceLevel.EXPLICIT))
    req.add_item(RequirementItem(type=RequirementType.ACTION, description="Persist incoming record to data store", confidence=ConfidenceLevel.EXPLICIT, risk=RiskLevel.MEDIUM))
    req.add_item(RequirementItem(type=RequirementType.ACTION, description="Dispatch outbound notification/message", confidence=ConfidenceLevel.EXPLICIT, risk=RiskLevel.MEDIUM))
    req.add_item(RequirementItem(type=RequirementType.DATA_SOURCE, description="Data store integration: PostgreSQL", confidence=ConfidenceLevel.EXPLICIT))
    req.add_item(RequirementItem(type=RequirementType.EXTERNAL_SERVICE, description="External service integration: WhatsApp", confidence=ConfidenceLevel.EXPLICIT))
    req.add_item(RequirementItem(type=RequirementType.SUCCESS_CRITERIA, description="One record created and one message dispatched", confidence=ConfidenceLevel.INFERRED))

    spec_service = SpecificationService()
    spec = spec_service.create_specification_from_requirement(req)
    spec_service.submit_for_review(spec)
    spec_service.approve_specification(spec, version_number=1, approver="lead_engineer")
    return spec


# 1. Unapproved specification rejected
def test_planner_fails_on_unapproved_specification(planner):
    unapproved_spec = Specification(project_id=uuid4(), requirement_id=uuid4())
    assert unapproved_spec.status == SpecificationStatus.DRAFT

    with pytest.raises(InvariantViolationError, match="unapproved"):
        planner.create_plan(unapproved_spec)


# 2. Approved specification derives complete workflow plan
def test_planner_happy_path(planner, approved_specification):
    plan = planner.create_plan(approved_specification)

    assert plan.specification_id == approved_specification.id
    assert plan.specification_version == 1
    assert len(plan.nodes) == 3  # Trigger + PostgreSQL + WhatsApp
    assert len(plan.connections) == 2  # Trigger -> PostgreSQL -> WhatsApp

    node_types = [n.node_type for n in plan.nodes]
    assert "n8n-nodes-base.webhook" in node_types
    assert "n8n-nodes-base.postgres" in node_types
    assert "n8n-nodes-base.httpRequest" in node_types

    # Node retry policies
    pg_node = next(n for n in plan.nodes if n.node_type == "n8n-nodes-base.postgres")
    assert pg_node.retry_on_fail is True
    assert pg_node.max_retries == 3

    # Test scenarios generated
    assert len(plan.test_scenarios) > 0
    assert any("One record created" in s for s in plan.test_scenarios)

    # Dictionary serialization
    dict_repr = plan.to_dict()
    assert dict_repr["specification_version"] == 1
    assert len(dict_repr["nodes"]) == 3
    assert len(dict_repr["connections"]) == 2


# 3. Schedule trigger planning
def test_planner_schedule_trigger(planner):
    req = Requirement(project_id=uuid4(), original_request="Every Monday at 8:00 AM, send email.")
    req.add_item(RequirementItem(type=RequirementType.TRIGGER, description="Trigger on: Scheduled / Cron trigger", confidence=ConfidenceLevel.EXPLICIT))
    req.add_item(RequirementItem(type=RequirementType.EXTERNAL_SERVICE, description="External service integration: Email", confidence=ConfidenceLevel.EXPLICIT))

    spec_service = SpecificationService()
    spec = spec_service.create_specification_from_requirement(req)
    spec_service.submit_for_review(spec)
    spec_service.approve_specification(spec, version_number=1, approver="lead_engineer")

    plan = planner.create_plan(spec)
    assert any(n.node_type == "n8n-nodes-base.scheduleTrigger" for n in plan.nodes)
    assert any(n.node_type == "n8n-nodes-base.emailSend" for n in plan.nodes)


# 4. Capability Enforcement blocks unverified operations
def test_planner_capability_enforcement():
    # Empty registry with no verified operations
    empty_registry = CapabilityRegistry()
    strict_service = CapabilityEnforcementService(registry=empty_registry)
    strict_planner = WorkflowPlanner(capability_service=strict_service)

    req = Requirement(project_id=uuid4(), original_request="When webhook received, save data.")
    req.add_item(RequirementItem(type=RequirementType.TRIGGER, description="Trigger on: Webhook event", confidence=ConfidenceLevel.EXPLICIT))

    spec_service = SpecificationService()
    spec = spec_service.create_specification_from_requirement(req)
    spec_service.submit_for_review(spec)
    spec_service.approve_specification(spec, version_number=1, approver="lead_engineer")

    with pytest.raises(CapabilityEnforcementError, match="Capability check failed"):
        strict_planner.create_plan(spec)


# 5. Planner Agent Component
def test_planner_agent_component(planner, approved_specification):
    agent_planner = Planner(planner_service=planner)
    plan = agent_planner.plan(
        specification=approved_specification,
        workflow_name="Custom Lead Ingestion Pipeline",
    )

    assert plan is not None
    assert plan.workflow_name == "Custom Lead Ingestion Pipeline"
    assert len(plan.nodes) == 3
