"""Unit tests for Workflow aggregate and WorkflowVersion immutability."""

import pytest
from uuid import uuid4
from app.domain.enums import WorkflowStatus, WorkflowVersionStatus
from app.domain.errors import DomainValidationError, ImmutableArtifactError, InvariantViolationError
from app.domain.models.workflow import Workflow, WorkflowVersion


def test_workflow_version_lifecycle_and_immutability():
    wf_id = uuid4()
    spec_ver_id = uuid4()
    v1 = WorkflowVersion(
        workflow_id=wf_id,
        version_number=1,
        specification_version_id=spec_ver_id,
        definition={"nodes": ["TriggerNode", "ActionNode"]},
    )
    assert v1.status == WorkflowVersionStatus.DRAFT

    # Draft version can be modified
    v1.update_definition({"nodes": ["TriggerNode", "ActionNode", "FilterNode"]})
    assert len(v1.definition["nodes"]) == 3

    # Progress through lifecycle
    v1.validate()
    assert v1.status == WorkflowVersionStatus.VALIDATED

    v1.mark_tested()
    assert v1.status == WorkflowVersionStatus.TESTED

    # Marking approved locks the version
    v1.mark_approved()
    assert v1.status == WorkflowVersionStatus.APPROVED

    # Modifying approved version fails
    with pytest.raises(ImmutableArtifactError):
        v1.update_definition({"nodes": ["ExploitNode"]})

    # Deploying preserves immutability
    v1.mark_deployed()
    assert v1.status == WorkflowVersionStatus.DEPLOYED
    with pytest.raises(ImmutableArtifactError):
        v1.update_definition({"nodes": ["ChangedNode"]})


def test_workflow_operational_status_transitions():
    wf = Workflow(project_id=uuid4(), name="LeadSync")
    assert wf.status == WorkflowStatus.DRAFT

    spec_id = uuid4()
    v1 = wf.add_version(specification_version_id=spec_id, definition={"step": 1})

    # Cannot activate if current version is not deployed
    with pytest.raises(InvariantViolationError):
        wf.activate()

    # Progress version to DEPLOYED
    v1.validate()
    v1.mark_tested()
    v1.mark_approved()
    v1.mark_deployed()

    # Now activation succeeds
    wf.activate()
    assert wf.status == WorkflowStatus.ACTIVE

    wf.deactivate()
    assert wf.status == WorkflowStatus.INACTIVE

    wf.archive()
    assert wf.status == WorkflowStatus.ARCHIVED


def test_workflow_empty_name_fails():
    with pytest.raises(DomainValidationError):
        Workflow(project_id=uuid4(), name="   ")
