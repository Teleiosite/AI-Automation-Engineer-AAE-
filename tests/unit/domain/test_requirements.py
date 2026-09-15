"""Unit tests for Requirement domain models and invariants."""

import pytest
from uuid import uuid4
from app.domain.enums import ConfidenceLevel, RequirementType, RiskLevel
from app.domain.errors import DomainValidationError, InvariantViolationError
from app.domain.models.requirement import Requirement, RequirementItem


def test_requirement_item_creation():
    item = RequirementItem(
        type=RequirementType.BUSINESS_OBJECTIVE,
        description="Sync new leads from website to CRM",
        confidence=ConfidenceLevel.EXPLICIT,
        risk=RiskLevel.MEDIUM,
    )
    assert item.type == RequirementType.BUSINESS_OBJECTIVE
    assert item.confidence == ConfidenceLevel.EXPLICIT
    assert item.risk == RiskLevel.MEDIUM
    assert item.description == "Sync new leads from website to CRM"


def test_requirement_item_empty_description_fails():
    with pytest.raises(DomainValidationError):
        RequirementItem(
            type=RequirementType.TRIGGER,
            description="   ",
            confidence=ConfidenceLevel.EXPLICIT,
        )


def test_exact_risk_levels():
    # Enforces exact AAE risk terminology: LOW, MEDIUM, HIGH, CRITICAL
    assert [r.value for r in RiskLevel] == ["LOW", "MEDIUM", "HIGH", "CRITICAL"]


def test_requirement_aggregate_creation():
    req = Requirement(
        project_id=uuid4(),
        original_request="Please automate sending reports every Monday at 9am.",
    )
    assert req.version == 1
    assert req.original_request == "Please automate sending reports every Monday at 9am."
    assert not req.has_unresolved_conflicts()
    assert not req.has_ambiguities()


def test_requirement_empty_request_fails():
    with pytest.raises(DomainValidationError):
        Requirement(project_id=uuid4(), original_request="")


def test_requirement_conflict_blocks_specification():
    req = Requirement(
        project_id=uuid4(),
        original_request="Send report instantly and also wait 30 minutes.",
    )
    req.add_item(RequirementItem(
        type=RequirementType.ACTION,
        description="Timing conflict detected",
        confidence=ConfidenceLevel.CONFLICTING,
        risk=RiskLevel.HIGH,
    ))
    assert req.has_unresolved_conflicts()
    with pytest.raises(InvariantViolationError):
        req.assert_ready_for_specification()


def test_requirement_ambiguity_blocks_specification():
    req = Requirement(
        project_id=uuid4(),
        original_request="Send notifications to whoever needs them.",
    )
    req.add_item(RequirementItem(
        type=RequirementType.OUTPUT,
        description="Recipient unknown",
        confidence=ConfidenceLevel.UNKNOWN,
        risk=RiskLevel.HIGH,
    ))
    assert req.has_ambiguities()
    with pytest.raises(InvariantViolationError):
        req.assert_ready_for_specification()
