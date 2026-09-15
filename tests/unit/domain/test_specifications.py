"""Unit tests for Specification domain models and invariants."""

import pytest
from uuid import uuid4
from app.domain.enums import SpecificationStatus
from app.domain.errors import ImmutableArtifactError, InvariantViolationError
from app.domain.models.specification import Specification


def test_specification_lifecycle():
    spec = Specification(project_id=uuid4(), requirement_id=uuid4())
    assert spec.status == SpecificationStatus.DRAFT
    assert not spec.is_construction_authorized()

    v1 = spec.add_version({"objective": "Send weekly email"})
    assert v1.version_number == 1
    assert not v1.is_approved

    # Modifying draft version is allowed
    v1.update_content({"objective": "Send weekly email updated"})
    assert v1.structured_content["objective"] == "Send weekly email updated"

    # Approving freezes the version and authorizes construction
    spec.approve(1)
    assert spec.status == SpecificationStatus.APPROVED
    assert v1.is_approved
    assert spec.is_construction_authorized()

    # Once approved, modifying that version raises ImmutableArtifactError
    with pytest.raises(ImmutableArtifactError):
        v1.update_content({"objective": "Attempted silent mutation"})


def test_specification_version_increment():
    spec = Specification(project_id=uuid4(), requirement_id=uuid4())
    v1 = spec.add_version({"v": 1})
    spec.approve(1)

    # Adding revision increments version and moves specification back to draft
    v2 = spec.add_version({"v": 2})
    assert v2.version_number == 2
    assert spec.current_version_number == 2
    assert spec.status == SpecificationStatus.DRAFT
    assert not spec.is_construction_authorized()


def test_approve_nonexistent_version_fails():
    spec = Specification(project_id=uuid4(), requirement_id=uuid4())
    with pytest.raises(InvariantViolationError):
        spec.approve(99)
