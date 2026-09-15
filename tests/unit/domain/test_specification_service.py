"""Unit tests for SpecificationService, Human Approval Gate, and Drift Detection (Phase 8)."""

from uuid import uuid4
import pytest

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
from app.domain.models.requirement import Requirement, RequirementItem
from app.domain.services.audit_service import AuditService
from app.domain.services.specification_service import SpecificationService
from app.agents.approval_manager import ApprovalManager


@pytest.fixture
def recorded_audit_events():
    events = []
    def sink(event):
        events.append(event)
    return events, sink


@pytest.fixture
def audit_service(recorded_audit_events):
    _, sink = recorded_audit_events
    return AuditService(sink=sink)


@pytest.fixture
def spec_service(audit_service) -> SpecificationService:
    return SpecificationService(audit_service=audit_service)


@pytest.fixture
def valid_requirement() -> Requirement:
    req = Requirement(
        project_id=uuid4(),
        original_request="Whenever contact form is submitted, save to PostgreSQL and send WhatsApp confirmation.",
    )
    req.add_item(
        RequirementItem(
            type=RequirementType.TRIGGER,
            description="Trigger on: Website form submission",
            confidence=ConfidenceLevel.EXPLICIT,
        )
    )
    req.add_item(
        RequirementItem(
            type=RequirementType.ACTION,
            description="Persist incoming record to data store",
            confidence=ConfidenceLevel.EXPLICIT,
            risk=RiskLevel.MEDIUM,
        )
    )
    req.add_item(
        RequirementItem(
            type=RequirementType.ACTION,
            description="Dispatch outbound notification/message",
            confidence=ConfidenceLevel.EXPLICIT,
            risk=RiskLevel.MEDIUM,
        )
    )
    req.add_item(
        RequirementItem(
            type=RequirementType.DATA_SOURCE,
            description="Data store integration: PostgreSQL",
            confidence=ConfidenceLevel.EXPLICIT,
        )
    )
    req.add_item(
        RequirementItem(
            type=RequirementType.EXTERNAL_SERVICE,
            description="External service integration: WhatsApp",
            confidence=ConfidenceLevel.EXPLICIT,
        )
    )
    req.add_item(
        RequirementItem(
            type=RequirementType.SUCCESS_CRITERIA,
            description="One record created and one message dispatched",
            confidence=ConfidenceLevel.INFERRED,
        )
    )
    return req


# 1. Happy Path: Valid requirement to structured specification
def test_create_specification_from_valid_requirement(spec_service, valid_requirement, recorded_audit_events):
    events, _ = recorded_audit_events
    spec = spec_service.create_specification_from_requirement(valid_requirement)

    assert spec.status == SpecificationStatus.DRAFT
    assert spec.current_version_number == 1
    assert len(spec.versions) == 1

    ver = spec.get_current_version()
    assert ver is not None
    assert ver.is_approved is False
    assert ver.structured_content["trigger"] == "Trigger on: Website form submission"
    assert "PostgreSQL" in ver.structured_content["data_stores"][0]["name"]
    assert "WhatsApp" in ver.structured_content["external_services"][0]["name"]
    assert "content_hash" in ver.structured_content
    assert spec.is_construction_authorized() is False

    # Audit event recorded
    assert any(e.event_type == "workflow.specification.created" for e in events)


# 2. Block specification on unresolved ambiguities or conflicts
def test_create_specification_fails_on_unresolved_ambiguity(spec_service, valid_requirement):
    valid_requirement.add_ambiguity("Target table unspecified")

    # Strict mode refuses generation
    with pytest.raises(InvariantViolationError):
        spec_service.create_specification_from_requirement(valid_requirement, allow_draft_on_ambiguity=False)

    # Permissive draft mode sets status to CLARIFICATION_REQUIRED
    spec = spec_service.create_specification_from_requirement(valid_requirement, allow_draft_on_ambiguity=True)
    assert spec.status == SpecificationStatus.CLARIFICATION_REQUIRED


# 3. Submit for review happy path & gap prevention
def test_submit_for_review_lifecycle(spec_service, valid_requirement):
    spec = spec_service.create_specification_from_requirement(valid_requirement)
    assert spec.status == SpecificationStatus.DRAFT

    spec_service.submit_for_review(spec, actor="agent_007")
    assert spec.status == SpecificationStatus.READY_FOR_REVIEW

    # With ambiguities, review submission is blocked
    ambiguous_req = Requirement(project_id=uuid4(), original_request="Unspecified action")
    ambiguous_req.add_ambiguity("Unspecified action")
    spec_ambiguous = spec_service.create_specification_from_requirement(ambiguous_req, allow_draft_on_ambiguity=True)
    with pytest.raises(InvariantViolationError, match="unresolved ambiguities"):
        spec_service.submit_for_review(spec_ambiguous)


# 4. Human Approval Gate: issues token, locks version, authorizes construction
def test_human_approval_gate(spec_service, valid_requirement, recorded_audit_events):
    events, _ = recorded_audit_events
    spec = spec_service.create_specification_from_requirement(valid_requirement)
    spec_service.submit_for_review(spec)

    # Silence is not approval
    with pytest.raises(DomainValidationError, match="cannot be empty"):
        spec_service.approve_specification(spec, version_number=1, approver="")

    approval = spec_service.approve_specification(
        spec,
        version_number=1,
        approver="lead_engineer_bob",
        comments="Approved for development",
    )

    assert spec.status == SpecificationStatus.APPROVED
    assert spec.is_construction_authorized() is True
    assert spec.get_current_version().is_approved is True

    # Approval token verified
    assert approval.target_type == "specification"
    assert approval.target_id == spec.id
    assert approval.target_version == 1
    assert approval.actor == "lead_engineer_bob"
    assert approval.decision == ApprovalDecision.APPROVED
    assert approval.status == ApprovalStatus.ACTIVE

    # Audit event recorded
    assert any(e.event_type == "approval.created" and e.actor == "lead_engineer_bob" for e in events)


# 5. Approved version is immutable
def test_approved_version_immutability(spec_service, valid_requirement):
    spec = spec_service.create_specification_from_requirement(valid_requirement)
    spec_service.submit_for_review(spec)
    spec_service.approve_specification(spec, version_number=1, approver="lead_engineer_bob")

    ver = spec.get_version(1)
    with pytest.raises(ImmutableArtifactError, match="locked"):
        ver.update_content({"tampered": True})


# 6. Version lineage preserved upon requirement modification
def test_new_version_preserves_history(spec_service, valid_requirement):
    spec = spec_service.create_specification_from_requirement(valid_requirement)
    spec_service.submit_for_review(spec)
    spec_service.approve_specification(spec, version_number=1, approver="lead_engineer_bob")

    # Add a new requirement item and create version 2
    valid_requirement.add_item(
        RequirementItem(
            type=RequirementType.EXTERNAL_SERVICE,
            description="External service integration: Slack",
            confidence=ConfidenceLevel.EXPLICIT,
        )
    )

    ver2 = spec_service.create_new_version(spec, valid_requirement, author="lead_engineer_bob")
    assert ver2.version_number == 2
    assert ver2.is_approved is False
    assert spec.current_version_number == 2
    assert spec.status == SpecificationStatus.DRAFT

    # Version 1 remains frozen and approved
    assert spec.get_version(1).is_approved is True


# 7. Rejection & Changes Requested
def test_rejection_and_changes_requested(spec_service, valid_requirement):
    spec = spec_service.create_specification_from_requirement(valid_requirement)
    spec_service.submit_for_review(spec)

    spec_service.request_changes(spec, actor="reviewer", feedback="Please add rate limiting")
    assert spec.status == SpecificationStatus.CLARIFICATION_REQUIRED

    spec_service.reject_specification(spec, rejecter="admin", reason="Project cancelled")
    assert spec.status == SpecificationStatus.REJECTED


# 8. Drift Detection
def test_detect_drift(spec_service, valid_requirement):
    spec = spec_service.create_specification_from_requirement(valid_requirement)
    content = spec.get_current_version().structured_content

    # Fully compliant plan
    compliant_plan = {
        "data_stores": ["PostgreSQL"],
        "external_services": ["WhatsApp"],
        "has_destructive_operations": False,
        "planned_actions": ["store record", "send message"],
    }
    drift = spec_service.detect_drift(content, compliant_plan)
    assert len(drift) == 0

    # Deviant plan: unauthorized service and unauthorized destructive operation
    deviant_plan = {
        "data_stores": ["PostgreSQL", "MongoDB"],
        "external_services": ["WhatsApp", "Stripe"],
        "has_destructive_operations": True,
        "planned_actions": ["store record"],
    }
    drift_deviant = spec_service.detect_drift(content, deviant_plan)
    assert len(drift_deviant) >= 3
    assert any("MongoDB" in d for d in drift_deviant)
    assert any("Stripe" in d for d in drift_deviant)
    assert any("destructive" in d.lower() for d in drift_deviant)


# 9. ApprovalManager Agent Component
def test_approval_manager_component(spec_service, valid_requirement):
    manager = ApprovalManager(spec_service)
    spec = spec_service.create_specification_from_requirement(valid_requirement)

    # 1. Request review
    manager.request_approval(spec, actor="agent_spec_writer")
    assert spec.status == SpecificationStatus.READY_FOR_REVIEW

    # 2. Record approval decision
    approval = manager.record_decision(
        spec,
        version_number=1,
        approver="lead_architect",
        decision="APPROVED",
        comments="Looks good to build",
    )
    assert approval is not None
    assert approval.actor == "lead_architect"
    assert spec.status == SpecificationStatus.APPROVED
    assert spec.is_construction_authorized() is True
