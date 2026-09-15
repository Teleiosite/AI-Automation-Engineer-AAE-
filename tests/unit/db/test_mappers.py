"""Unit tests for domain <-> persistence mappers."""

from datetime import datetime, timezone
from uuid import uuid4
from app.db.mappers import (
    approval_to_domain,
    approval_to_model,
    audit_event_to_domain,
    audit_event_to_model,
    deployment_to_domain,
    deployment_to_model,
    diagnostic_finding_to_domain,
    diagnostic_finding_to_model,
    execution_result_to_domain,
    execution_to_domain,
    execution_to_model,
    failure_record_to_domain,
    failure_record_to_model,
    project_to_domain,
    project_to_model,
    repair_attempt_to_domain,
    repair_attempt_to_model,
    requirement_item_to_domain,
    requirement_item_to_model,
    requirement_to_domain,
    requirement_to_model,
    specification_to_domain,
    specification_to_model,
    specification_version_to_domain,
    specification_version_to_model,
    workflow_to_domain,
    workflow_to_model,
    workflow_version_to_domain,
    workflow_version_to_model,
)
from app.domain.enums import (
    ApprovalDecision,
    ApprovalStatus,
    ApprovalTargetType,
    ConfidenceLevel,
    DeploymentStatus,
    ExecutionStatus,
    FailureCategory,
    FailureSeverity,
    RequirementType,
    RiskLevel,
    SemanticStatus,
    SpecificationStatus,
    TechnicalStatus,
    TriggerType,
    WorkflowStatus,
    WorkflowVersionStatus,
)
from app.domain.models.approval import Approval
from app.domain.models.audit import AuditEvent
from app.domain.models.deployment import Deployment
from app.domain.models.diagnostic import DiagnosticFinding, FailureRecord
from app.domain.models.execution import Execution, ExecutionResult
from app.domain.models.project import Project
from app.domain.models.repair import RepairAttempt
from app.domain.models.requirement import Requirement, RequirementItem
from app.domain.models.specification import Specification, SpecificationVersion
from app.domain.models.workflow import Workflow, WorkflowVersion


def test_project_mapper_roundtrip():
    entity = Project(name="TestProj", description="Test Desc", is_active=True)
    model = project_to_model(entity)
    restored = project_to_domain(model)

    assert restored.id == entity.id
    assert restored.name == entity.name
    assert restored.description == entity.description
    assert restored.is_active == entity.is_active
    assert restored.created_at == entity.created_at


def test_requirement_and_item_mapper_roundtrip():
    req_id = uuid4()
    item = RequirementItem(
        type=RequirementType.TRIGGER,
        description="On Webhook",
        confidence=ConfidenceLevel.EXPLICIT,
        risk=RiskLevel.MEDIUM,
        notes="webhook payload",
    )
    req = Requirement(
        id=req_id,
        project_id=uuid4(),
        original_request="Build webhook sync",
        created_by="lead_eng",
        version=1,
        items=[item],
        assumptions=["JSON payload"],
        ambiguities=["Rate limit unspecified"],
        conflicts=[],
    )

    model = requirement_to_model(req)
    restored = requirement_to_domain(model)

    assert restored.id == req.id
    assert restored.project_id == req.project_id
    assert restored.original_request == req.original_request
    assert restored.version == 1
    assert len(restored.items) == 1
    assert restored.items[0].description == "On Webhook"
    assert restored.items[0].risk == RiskLevel.MEDIUM
    assert restored.items[0].notes == "webhook payload"
    assert restored.assumptions == ["JSON payload"]
    assert restored.ambiguities == ["Rate limit unspecified"]


def test_specification_and_version_mapper_roundtrip():
    spec_id = uuid4()
    ver = SpecificationVersion(
        specification_id=spec_id,
        version_number=1,
        structured_content={"triggers": ["webhook"], "actions": ["transform", "post"]},
        is_approved=True,
    )
    spec = Specification(
        id=spec_id,
        project_id=uuid4(),
        requirement_id=uuid4(),
        status=SpecificationStatus.APPROVED,
        current_version_number=1,
        versions=[ver],
    )

    model = specification_to_model(spec)
    restored = specification_to_domain(model)

    assert restored.id == spec.id
    assert restored.status == SpecificationStatus.APPROVED
    assert restored.current_version_number == 1
    assert len(restored.versions) == 1
    assert restored.versions[0].version_number == 1
    assert restored.versions[0].structured_content == {"triggers": ["webhook"], "actions": ["transform", "post"]}
    assert restored.versions[0].is_approved is True


def test_workflow_and_version_mapper_roundtrip():
    wf_id = uuid4()
    ver = WorkflowVersion(
        workflow_id=wf_id,
        version_number=1,
        specification_version_id=uuid4(),
        definition={"nodes": [{"id": "1", "name": "Start"}]},
        status=WorkflowVersionStatus.APPROVED,
        change_reason="Initial build",
        created_by="builder_agent",
        provider_version_id="n8n_v1",
    )
    wf = Workflow(
        id=wf_id,
        project_id=uuid4(),
        name="SyncWorkflow",
        environment="staging",
        status=WorkflowStatus.ACTIVE,
        current_version_id=ver.id,
        versions=[ver],
    )

    model = workflow_to_model(wf)
    restored = workflow_to_domain(model)

    assert restored.id == wf.id
    assert restored.name == "SyncWorkflow"
    assert restored.status == WorkflowStatus.ACTIVE
    assert restored.current_version_id == ver.id
    assert len(restored.versions) == 1
    assert restored.versions[0].version_number == 1
    assert restored.versions[0].status == WorkflowVersionStatus.APPROVED
    assert restored.versions[0].provider_version_id == "n8n_v1"


def test_execution_and_result_mapper_roundtrip():
    res = ExecutionResult(
        technical_status=TechnicalStatus.SUCCESS,
        semantic_status=SemanticStatus.SATISFIED,
        duration_ms=245.5,
        output_data={"result": "ok"},
        error_message=None,
        error_details=None,
    )
    exec_entity = Execution(
        workflow_id=uuid4(),
        workflow_version_id=uuid4(),
        status=ExecutionStatus.SUCCESS,
        trigger_type=TriggerType.WEBHOOK,
        finished_at=datetime.now(timezone.utc),
        result=res,
        correlation_id="corr-12345",
    )

    model = execution_to_model(exec_entity)
    restored = execution_to_domain(model)

    assert restored.id == exec_entity.id
    assert restored.status == ExecutionStatus.SUCCESS
    assert restored.trigger_type == TriggerType.WEBHOOK
    assert restored.correlation_id == "corr-12345"
    assert restored.result is not None
    assert restored.result.technical_status == TechnicalStatus.SUCCESS
    assert restored.result.semantic_status == SemanticStatus.SATISFIED
    assert restored.result.duration_ms == 245.5
    assert restored.result.output_data == {"result": "ok"}


def test_approval_mapper_roundtrip():
    approval = Approval(
        target_type=ApprovalTargetType.WORKFLOW_VERSION,
        target_id=uuid4(),
        target_version=2,
        actor="lead_devops",
        action="deploy",
        environment="production",
        decision=ApprovalDecision.APPROVED,
        status=ApprovalStatus.ACTIVE,
        decided_at=datetime.now(timezone.utc),
        comments="Approved for release",
    )

    model = approval_to_model(approval)
    restored = approval_to_domain(model)

    assert restored.id == approval.id
    assert restored.target_type == ApprovalTargetType.WORKFLOW_VERSION
    assert restored.target_version == 2
    assert restored.actor == "lead_devops"
    assert restored.decision == ApprovalDecision.APPROVED
    assert restored.status == ApprovalStatus.ACTIVE
    assert restored.comments == "Approved for release"


def test_deployment_mapper_roundtrip():
    deployment = Deployment(
        workflow_id=uuid4(),
        workflow_version_id=uuid4(),
        workflow_version_number=2,
        target_environment="production",
        deployed_by="devops_service",
        approval_id=uuid4(),
        status=DeploymentStatus.DEPLOYED,
        deployed_at=datetime.now(timezone.utc),
    )

    model = deployment_to_model(deployment)
    restored = deployment_to_domain(model)

    assert restored.id == deployment.id
    assert restored.workflow_version_number == 2
    assert restored.target_environment == "production"
    assert restored.status == DeploymentStatus.DEPLOYED
    assert restored.approval_id == deployment.approval_id


def test_diagnostic_and_failure_mapper_roundtrip():
    failure = FailureRecord(
        execution_id=uuid4(),
        category=FailureCategory.INTEGRATION_ERROR,
        severity=FailureSeverity.HIGH,
        failed_component="HTTP Request Node",
        message="504 Gateway Timeout",
        technical_details={"code": 504, "endpoint": "/api/sync"},
    )
    f_model = failure_record_to_model(failure)
    f_restored = failure_record_to_domain(f_model)

    assert f_restored.id == failure.id
    assert f_restored.category == FailureCategory.INTEGRATION_ERROR
    assert f_restored.severity == FailureSeverity.HIGH
    assert f_restored.technical_details == {"code": 504, "endpoint": "/api/sync"}

    finding = DiagnosticFinding(
        failure_id=failure.id,
        likely_cause="Downstream endpoint unresponsive",
        confidence=ConfidenceLevel.EXPLICIT,
        recommended_action="Increase timeout and enable retry",
    )
    d_model = diagnostic_finding_to_model(finding)
    d_restored = diagnostic_finding_to_domain(d_model)

    assert d_restored.id == finding.id
    assert d_restored.failure_id == failure.id
    assert d_restored.confidence == ConfidenceLevel.EXPLICIT


def test_repair_attempt_mapper_roundtrip():
    repair = RepairAttempt(
        workflow_id=uuid4(),
        target_version_number=2,
        failure_id=uuid4(),
        diagnostic_id=uuid4(),
        proposed_change={"timeout": 30, "retry": 3},
        risk=RiskLevel.LOW,
        status="PROPOSED",
    )
    model = repair_attempt_to_model(repair)
    restored = repair_attempt_to_domain(model)

    assert restored.id == repair.id
    assert restored.target_version_number == 2
    assert restored.proposed_change == {"timeout": 30, "retry": 3}
    assert restored.risk == RiskLevel.LOW


def test_audit_event_mapper_roundtrip():
    event = AuditEvent(
        event_type="DEPLOYMENT_AUTHORIZED",
        actor="devops_lead",
        target_type="WorkflowVersion",
        target_id="wf-12345",
        correlation_id="corr-987",
        outcome="SUCCESS",
        metadata={"version": 2, "env": "production"},
    )
    model = audit_event_to_model(event)
    restored = audit_event_to_domain(model)

    assert restored.id == event.id
    assert restored.event_type == "DEPLOYMENT_AUTHORIZED"
    assert restored.actor == "devops_lead"
    assert restored.metadata == {"version": 2, "env": "production"}
