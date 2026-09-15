"""Unit tests for DeploymentAuthorizationPolicy cross-aggregate governance."""

import pytest
from uuid import uuid4
from app.domain.enums import AgentState, ApprovalStatus, ApprovalTargetType, DeploymentStatus, WorkflowVersionStatus
from app.domain.errors import (
    ApprovalRequiredError,
    InvalidStateTransitionError,
    InvariantViolationError,
    StaleApprovalError,
)
from app.domain.models.approval import Approval
from app.domain.models.deployment import Deployment
from app.domain.models.workflow import Workflow, WorkflowVersion
from app.domain.services.deployment_policy import DeploymentAuthorizationPolicy


def test_deployment_authorization_happy_path():
    wf = Workflow(project_id=uuid4(), name="DeploySync")
    spec_ver_id = uuid4()
    ver = wf.add_version(specification_version_id=spec_ver_id, definition={"steps": ["task"]})
    ver.validate()
    ver.mark_tested()
    ver.mark_approved()

    deployment = Deployment(
        workflow_id=wf.id,
        workflow_version_id=ver.id,
        workflow_version_number=ver.version_number,
        target_environment="production",
        deployed_by="devops_agent",
    )

    approval = Approval(
        target_type=ApprovalTargetType.WORKFLOW_VERSION,
        target_id=wf.id,
        target_version=ver.version_number,
        environment="production",
        actor="lead_devops",
    )
    approval.approve()

    # Policy authorizes deployment: agent_state is APPROVED, matching approval exists
    DeploymentAuthorizationPolicy.authorize_deployment(
        deployment=deployment,
        workflow=wf,
        workflow_version=ver,
        approval=approval,
        agent_state=AgentState.APPROVED,
    )

    # Deployment transitioned to IN_PROGRESS
    assert deployment.status == DeploymentStatus.IN_PROGRESS
    assert deployment.approval_id == approval.id
    # Approval was consumed to prevent replay
    assert approval.status == ApprovalStatus.CONSUMED
    assert approval.consumed_by_action_id == deployment.id


def test_deployment_rejected_when_agent_not_in_approved_state():
    wf = Workflow(project_id=uuid4(), name="DeploySync")
    ver = wf.add_version(specification_version_id=uuid4(), definition={"s": 1})
    ver.validate()
    ver.mark_tested()
    ver.mark_approved()

    deployment = Deployment(
        workflow_id=wf.id,
        workflow_version_id=ver.id,
        workflow_version_number=ver.version_number,
        target_environment="production",
        deployed_by="devops_agent",
    )

    approval = Approval(
        target_type=ApprovalTargetType.WORKFLOW_VERSION,
        target_id=wf.id,
        target_version=ver.version_number,
        environment="production",
        actor="lead_devops",
    )
    approval.approve()

    # Must fail if AgentState is not APPROVED (e.g. TESTING or BUILDING)
    with pytest.raises(InvalidStateTransitionError):
        DeploymentAuthorizationPolicy.authorize_deployment(
            deployment=deployment,
            workflow=wf,
            workflow_version=ver,
            approval=approval,
            agent_state=AgentState.TESTING,
        )


def test_deployment_rejected_without_approval():
    wf = Workflow(project_id=uuid4(), name="DeploySync")
    ver = wf.add_version(specification_version_id=uuid4(), definition={"s": 1})
    ver.validate()
    ver.mark_tested()
    ver.mark_approved()

    deployment = Deployment(
        workflow_id=wf.id,
        workflow_version_id=ver.id,
        workflow_version_number=ver.version_number,
        target_environment="production",
        deployed_by="devops_agent",
    )

    with pytest.raises(ApprovalRequiredError):
        DeploymentAuthorizationPolicy.authorize_deployment(
            deployment=deployment,
            workflow=wf,
            workflow_version=ver,
            approval=None,
            agent_state=AgentState.APPROVED,
        )


def test_deployment_rejected_on_version_mismatch():
    wf = Workflow(project_id=uuid4(), name="DeploySync")
    ver1 = wf.add_version(specification_version_id=uuid4(), definition={"s": 1})
    ver1.validate()
    ver1.mark_tested()
    ver1.mark_approved()

    ver2 = wf.add_version(specification_version_id=uuid4(), definition={"s": 2})
    ver2.validate()
    ver2.mark_tested()
    ver2.mark_approved()

    deployment_v2 = Deployment(
        workflow_id=wf.id,
        workflow_version_id=ver2.id,
        workflow_version_number=ver2.version_number,
        target_environment="production",
        deployed_by="devops_agent",
    )

    # Approval was for version 1
    approval_v1 = Approval(
        target_type=ApprovalTargetType.WORKFLOW_VERSION,
        target_id=wf.id,
        target_version=1,
        environment="production",
        actor="lead_devops",
    )
    approval_v1.approve()

    # Attempting to deploy v2 using approval for v1 must fail
    with pytest.raises(StaleApprovalError):
        DeploymentAuthorizationPolicy.authorize_deployment(
            deployment=deployment_v2,
            workflow=wf,
            workflow_version=ver2,
            approval=approval_v1,
            agent_state=AgentState.APPROVED,
        )
