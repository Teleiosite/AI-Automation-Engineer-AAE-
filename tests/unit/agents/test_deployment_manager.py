"""Unit tests for DeploymentManager service and DeploymentManagerAgent (Phase 17)."""

from uuid import uuid4
import pytest

from app.agents.deployment_manager import DeploymentManagerAgent
from app.domain.enums import (
    AgentState,
    ApprovalDecision,
    ApprovalStatus,
    ApprovalTargetType,
    DeploymentStatus,
    WorkflowStatus,
    WorkflowVersionStatus,
)
from app.domain.errors import (
    ApprovalRequiredError,
    DomainValidationError,
    StaleApprovalError,
)
from app.domain.models.approval import Approval
from app.domain.models.workflow import Workflow
from app.domain.services.audit_service import AuditService
from app.domain.services.deployment_manager import DeploymentManager


@pytest.fixture
def sample_workflow() -> Workflow:
    wf = Workflow(project_id=uuid4(), name="Customer Payment Pipeline")
    wf.add_version(
        specification_version_id=uuid4(),
        definition={"name": "Customer Payment Pipeline", "nodes": []},
        change_reason="Initial build",
    )
    return wf


def test_deployment_development_happy_path(sample_workflow):
    manager = DeploymentManager()
    version = sample_workflow.get_current_version()
    version.validate()
    version.mark_tested()

    dep = manager.deploy(
        workflow=sample_workflow,
        version_number=1,
        target_environment="development",
        deployed_by="engineer-1",
    )

    assert dep.status == DeploymentStatus.DEPLOYED
    assert dep.target_environment == "development"
    assert sample_workflow.environment == "development"
    assert sample_workflow.status == WorkflowStatus.ACTIVE
    assert version.status == WorkflowVersionStatus.DEPLOYED


def test_deployment_production_without_approval_blocked(sample_workflow):
    manager = DeploymentManager()
    version = sample_workflow.get_current_version()
    version.validate()
    version.mark_tested()
    version.mark_approved()

    with pytest.raises(ApprovalRequiredError):
        manager.deploy(
            workflow=sample_workflow,
            version_number=1,
            target_environment="production",
            approval=None,  # Missing approval
        )


def test_deployment_production_with_stale_or_invalid_approval_blocked(sample_workflow):
    manager = DeploymentManager()
    version = sample_workflow.get_current_version()
    version.validate()
    version.mark_tested()
    version.mark_approved()

    # Create approval for a DIFFERENT workflow
    stale_approval = Approval(
        target_type=ApprovalTargetType.WORKFLOW_VERSION,
        target_id=uuid4(),  # Different ID!
        target_version=1,
        actor="manager-1",
        action="deploy",
        environment="production",
        status=ApprovalStatus.ACTIVE,
        decision=ApprovalDecision.APPROVED,
    )

    with pytest.raises(StaleApprovalError):
        manager.deploy(
            workflow=sample_workflow,
            version_number=1,
            target_environment="production",
            approval=stale_approval,
            agent_state=AgentState.APPROVED,
        )


def test_deployment_production_happy_path(sample_workflow):
    manager = DeploymentManager()
    version = sample_workflow.get_current_version()
    version.validate()
    version.mark_tested()
    version.mark_approved()

    valid_approval = Approval(
        target_type=ApprovalTargetType.WORKFLOW_VERSION,
        target_id=sample_workflow.id,
        target_version=1,
        actor="ops-director",
        action="deploy",
        environment="production",
        status=ApprovalStatus.ACTIVE,
        decision=ApprovalDecision.APPROVED,
    )

    dep = manager.deploy(
        workflow=sample_workflow,
        version_number=1,
        target_environment="production",
        deployed_by="devops-lead",
        approval=valid_approval,
        agent_state=AgentState.APPROVED,
    )

    assert dep.status == DeploymentStatus.DEPLOYED
    assert dep.target_environment == "production"
    assert dep.approval_id == valid_approval.id
    # Ensure approval is consumed to prevent replay attacks
    assert valid_approval.status == ApprovalStatus.CONSUMED
    assert sample_workflow.environment == "production"
    assert sample_workflow.status == WorkflowStatus.ACTIVE


def test_deployment_rollback(sample_workflow):
    manager = DeploymentManager()
    v1 = sample_workflow.get_current_version()
    v1.validate()
    v1.mark_tested()
    v1.mark_approved()

    # Initial dev deployment
    dep1 = manager.deploy(
        workflow=sample_workflow,
        version_number=1,
        target_environment="development",
    )
    assert dep1.status == DeploymentStatus.DEPLOYED

    # Add v2
    v2 = sample_workflow.add_version(
        specification_version_id=uuid4(),
        definition={"name": "v2 bad", "nodes": []},
        change_reason="v2 update",
    )
    v2.validate()
    v2.mark_tested()
    v2.mark_approved()

    dep2 = manager.deploy(
        workflow=sample_workflow,
        version_number=2,
        target_environment="development",
    )
    assert dep2.status == DeploymentStatus.DEPLOYED

    # Rollback deployment to v1
    rollback_dep = manager.rollback_deployment(
        workflow=sample_workflow,
        active_deployment=dep2,
        target_version_number=1,
        reason="v2 had regression",
    )

    assert dep2.status == DeploymentStatus.ROLLED_BACK
    assert rollback_dep.status == DeploymentStatus.DEPLOYED
    assert rollback_dep.workflow_version_number == 1
    assert sample_workflow.status == WorkflowStatus.ACTIVE


def test_deployment_invalid_environment_rejected(sample_workflow):
    manager = DeploymentManager()
    with pytest.raises(DomainValidationError):
        manager.deploy(
            workflow=sample_workflow,
            version_number=1,
            target_environment="unauthorized_cloud",
        )


def test_deployment_agent_component(sample_workflow):
    agent = DeploymentManagerAgent()
    v1 = sample_workflow.get_current_version()
    v1.validate()
    v1.mark_tested()

    dep = agent.deploy(
        workflow=sample_workflow,
        version_number=1,
        target_environment="development",
    )
    assert dep.status == DeploymentStatus.DEPLOYED


def test_deployment_audit_event_logging(sample_workflow):
    audit_service = AuditService()
    manager = DeploymentManager(audit_service=audit_service)
    v1 = sample_workflow.get_current_version()
    v1.validate()
    v1.mark_tested()

    manager.deploy(
        workflow=sample_workflow,
        version_number=1,
        target_environment="development",
        correlation_id="corr-dep-1",
    )

    events = audit_service.get_buffered_events()
    assert any(e.event_type == "deployment.executed" for e in events)
    dep_event = next(e for e in events if e.event_type == "deployment.executed")
    assert dep_event.correlation_id == "corr-dep-1"
    assert dep_event.metadata["environment"] == "development"
