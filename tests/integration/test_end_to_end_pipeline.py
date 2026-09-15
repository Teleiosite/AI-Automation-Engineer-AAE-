"""Integration tests for AAE Autonomous End-to-End Pipeline (Phase 21 / §56 CODEX_IMPLEMENTATION_PLAN.md)."""

import ast
from pathlib import Path
from uuid import uuid4
import pytest

from app.domain.enums import (
    ApprovalDecision,
    ApprovalStatus,
    RiskLevel,
    WorkflowStatus,
    WorkflowVersionStatus,
)
from app.domain.errors import ApprovalRequiredError
from app.domain.models.approval import Approval
from app.domain.models.project import Project
from app.domain.models.workflow import Workflow
from app.domain.services.end_to_end_pipeline import (
    EndToEndPipeline,
    EndToEndPipelineResult,
)
from app.domain.services.workflow_monitor import HealthStatus


def test_end_to_end_pipeline_domain_isolation():
    """Verify end_to_end_pipeline.py contains zero framework imports."""
    pipeline_path = Path("app/domain/services/end_to_end_pipeline.py")
    assert pipeline_path.exists()
    tree = ast.parse(pipeline_path.read_text(encoding="utf-8"))
    forbidden = {"fastapi", "sqlalchemy", "pydantic", "httpx", "n8n"}

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for name in node.names:
                root_pkg = name.name.split(".")[0]
                assert root_pkg not in forbidden, f"Forbidden import: {name.name}"
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                root_pkg = node.module.split(".")[0]
                assert root_pkg not in forbidden, f"Forbidden from-import: {node.module}"


def test_canonical_aae_demonstration_lifecycle():
    """Canonical AAE Demonstration (§56 CODEX_IMPLEMENTATION_PLAN.md).

    Tests:
    1. User request analysis
    2. Specification production
    3. Human approval gate
    4. Workflow planning
    5. Workflow building
    6. 7-layer validation
    7. Semantic testing
    8. Production deployment
    9. Operational monitoring
    10. Failure injection -> Diagnosis -> Repair -> Regression -> Re-deployment -> Success
    """
    pipeline = EndToEndPipeline()
    project_id = uuid4()
    user_request = (
        "When a new lead submits a website form, "
        "save the lead, "
        "send a welcome response, "
        "and notify the sales team."
    )

    result = pipeline.execute_lifecycle(
        project_id=project_id,
        user_request=user_request,
        approver="Lead Engineer",
        target_environment="production",
        simulate_failure_and_repair=True,
    )

    assert result.success is True
    assert result.workflow_name == "Lead Intake & Notification Automation"
    assert result.validation_passed is True
    assert result.tests_passed is True
    assert result.deployed_environment == "production"
    assert result.workflow_version == 2  # v1 deployed, then v2 repaired and re-deployed
    assert result.repair_successful is True
    assert result.health_status == HealthStatus.HEALTHY

    expected_stages = [
        "Requirement Analysis",
        "Specification Creation",
        "Human Approval Gate",
        "Workflow Planning",
        "Workflow Building",
        "Workflow Validation",
        "Technical & Semantic Testing",
        "Production Deployment",
        "Operational Telemetry & Monitoring",
        "Failure Injection & Diagnosis",
        "Surgical Repair",
        "Regression Testing",
    ]
    for stage in expected_stages:
        assert stage in result.stages_executed, f"Stage '{stage}' was not executed"


def test_unapproved_production_deployment_fails_closed():
    """Fail-closed safety: Direct production deployment without approval is blocked."""
    pipeline = EndToEndPipeline()
    project_id = uuid4()
    wf = Workflow(project_id=project_id, name="Unapproved Workflow")
    v1 = wf.add_version(
        specification_version_id=uuid4(),
        definition={"name": "Test", "nodes": [{"name": "Node1", "type": "n8n-nodes-base.webhook", "typeVersion": 1, "parameters": {}, "position": [100, 200]}], "connections": {}},
    )
    v1.validate()
    v1.mark_tested()
    v1.mark_approved()

    # Attempt deploy to production without Approval object
    with pytest.raises(ApprovalRequiredError, match="requires explicit approval"):
        pipeline.deployer.deploy(
            workflow=wf,
            version_number=1,
            target_environment="production",
            deployed_by="engineer",
            approval=None,
        )
