"""Integration tests for all 14 persistence tables and repositories."""

from datetime import datetime, timezone
from uuid import uuid4
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.base import Base
from app.db.repositories.approval_repo import ApprovalRepository
from app.db.repositories.audit_repo import AuditRepository
from app.db.repositories.deployment_repo import DeploymentRepository
from app.db.repositories.diagnostic_repo import DiagnosticRepository
from app.db.repositories.execution_repo import ExecutionRepository
from app.db.repositories.project_repo import ProjectRepository
from app.db.repositories.repair_repo import RepairRepository
from app.db.repositories.requirement_repo import RequirementRepository
from app.db.repositories.specification_repo import SpecificationRepository
from app.db.repositories.workflow_repo import WorkflowRepository
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
    TechnicalStatus,
    TriggerType,
)
from app.domain.models.approval import Approval
from app.domain.models.audit import AuditEvent
from app.domain.models.deployment import Deployment
from app.domain.models.diagnostic import DiagnosticFinding, FailureRecord
from app.domain.models.execution import Execution, ExecutionResult
from app.domain.models.project import Project
from app.domain.models.repair import RepairAttempt
from app.domain.models.requirement import Requirement, RequirementItem
from app.domain.models.specification import Specification
from app.domain.models.workflow import Workflow


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    s = session_factory()
    yield s
    s.close()


def test_full_domain_persistence_lifecycle(session):
    # 1. Project
    p_repo = ProjectRepository(session)
    project = p_repo.save(Project(name="CustomerSync", description="HubSpot sync"))
    assert project.id is not None
    assert p_repo.get_by_name("CustomerSync") is not None

    # 2. Requirement + RequirementItems
    r_repo = RequirementRepository(session)
    item = RequirementItem(
        type=RequirementType.TRIGGER,
        description="On new contact created in HubSpot",
        confidence=ConfidenceLevel.EXPLICIT,
        risk=RiskLevel.LOW,
    )
    req = Requirement(
        project_id=project.id,
        original_request="Sync new contacts from HubSpot to Postgres",
        items=[item],
        assumptions=["Contact has email"],
    )
    saved_req = r_repo.save(req)
    retrieved_req = r_repo.get(saved_req.id)
    assert retrieved_req is not None
    assert len(retrieved_req.items) == 1
    assert retrieved_req.items[0].description == "On new contact created in HubSpot"

    # 3. Specification + SpecificationVersion
    s_repo = SpecificationRepository(session)
    spec = Specification(project_id=project.id, requirement_id=saved_req.id)
    saved_spec = s_repo.save(spec)
    ver1 = s_repo.create_version_atomic(
        specification_id=saved_spec.id,
        structured_content={"triggers": ["webhook"], "actions": ["upsert"]},
        is_approved=True,
    )
    assert ver1.version_number == 1
    assert ver1.is_approved is True

    # 4. Workflow + WorkflowVersion
    w_repo = WorkflowRepository(session)
    wf = Workflow(project_id=project.id, name="HubSpotToPostgres")
    saved_wf = w_repo.save(wf)
    wf_ver1 = w_repo.create_version_atomic(
        workflow_id=saved_wf.id,
        specification_version_id=ver1.id,
        definition={"nodes": [{"id": "hubspot_trigger", "type": "webhook"}]},
    )
    assert wf_ver1.version_number == 1
    reloaded_wf = w_repo.get(saved_wf.id)
    assert reloaded_wf is not None
    assert reloaded_wf.current_version_id == wf_ver1.id

    # 5. Execution + ExecutionResult (embedded)
    e_repo = ExecutionRepository(session)
    result = ExecutionResult(
        technical_status=TechnicalStatus.SUCCESS,
        semantic_status=SemanticStatus.SATISFIED,
        duration_ms=150.0,
        output_data={"synced_records": 1},
    )
    execution = Execution(
        workflow_id=saved_wf.id,
        workflow_version_id=wf_ver1.id,
        status=ExecutionStatus.SUCCESS,
        trigger_type=TriggerType.WEBHOOK,
        finished_at=datetime.now(timezone.utc),
        result=result,
        correlation_id="corr-cust-001",
    )
    saved_exec = e_repo.save(execution)
    retrieved_exec = e_repo.get(saved_exec.id)
    assert retrieved_exec is not None
    assert retrieved_exec.result is not None
    assert retrieved_exec.result.technical_status == TechnicalStatus.SUCCESS
    assert retrieved_exec.result.semantic_status == SemanticStatus.SATISFIED

    # 6. Approval
    a_repo = ApprovalRepository(session)
    approval = Approval(
        target_type=ApprovalTargetType.WORKFLOW_VERSION,
        target_id=saved_wf.id,
        target_version=1,
        actor="chief_architect",
        action="deploy",
        environment="production",
    )
    approval.approve(comments="Validated on staging")
    saved_approval = a_repo.save(approval)
    assert saved_approval.decision == ApprovalDecision.APPROVED
    assert saved_approval.status == ApprovalStatus.ACTIVE

    # 7. Deployment
    d_repo = DeploymentRepository(session)
    deployment = Deployment(
        workflow_id=saved_wf.id,
        workflow_version_id=wf_ver1.id,
        workflow_version_number=1,
        target_environment="production",
        deployed_by="devops_agent",
        approval_id=saved_approval.id,
        status=DeploymentStatus.DEPLOYED,
        deployed_at=datetime.now(timezone.utc),
    )
    saved_deployment = d_repo.save(deployment)
    assert saved_deployment.id is not None
    assert saved_deployment.status == DeploymentStatus.DEPLOYED

    # 8. FailureRecord + DiagnosticFinding
    diag_repo = DiagnosticRepository(session)
    failure = FailureRecord(
        execution_id=saved_exec.id,
        category=FailureCategory.TIMEOUT,
        severity=FailureSeverity.MEDIUM,
        failed_component="Postgres Upsert Node",
        message="Connection timed out after 30s",
        technical_details={"timeout": 30},
    )
    saved_failure = diag_repo.save_failure(failure)
    assert saved_failure.id is not None

    finding = DiagnosticFinding(
        failure_id=saved_failure.id,
        likely_cause="Database connection pool exhausted",
        confidence=ConfidenceLevel.EXPLICIT,
        recommended_action="Increase pool_size or reduce hold duration",
    )
    saved_finding = diag_repo.save_finding(finding)
    assert saved_finding.id is not None

    # 9. RepairAttempt
    rep_repo = RepairRepository(session)
    repair = RepairAttempt(
        workflow_id=saved_wf.id,
        target_version_number=1,
        failure_id=saved_failure.id,
        diagnostic_id=saved_finding.id,
        proposed_change={"pool_size": 20},
        risk=RiskLevel.LOW,
        status="PROPOSED",
    )
    saved_repair = rep_repo.save(repair)
    assert saved_repair.id is not None
    assert saved_repair.status == "PROPOSED"

    # 10. AuditEvent (append-only)
    aud_repo = AuditRepository(session)
    audit = AuditEvent(
        event_type="WORKFLOW_DEPLOYED",
        actor="devops_agent",
        target_type="WorkflowVersion",
        target_id=str(wf_ver1.id),
        correlation_id="corr-cust-001",
        metadata={"environment": "production", "approval_id": str(saved_approval.id)},
    )
    saved_audit = aud_repo.append(audit)
    assert saved_audit.id is not None
    retrieved_audits = aud_repo.list_for_target("WorkflowVersion", str(wf_ver1.id))
    assert len(retrieved_audits) == 1
    assert retrieved_audits[0].event_type == "WORKFLOW_DEPLOYED"
