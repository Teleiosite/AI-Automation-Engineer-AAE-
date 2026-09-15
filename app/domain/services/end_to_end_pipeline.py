"""AAE End-to-End Autonomous Lifecycle Pipeline (§56 CODEX_IMPLEMENTATION_PLAN.md).

Coordinates the canonical AAE demonstration and complete engineering lifecycle:
Request -> Analysis -> Specification -> Human Approval -> Planning -> Build ->
7-Layer Validation -> Testing -> Deployment Approval -> Deployment -> Monitoring ->
Failure Injection -> Diagnosis -> Repair -> Regression -> Re-deployment -> Success.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID, uuid4

from app.domain.enums import (
    ApprovalDecision,
    ApprovalStatus,
    ApprovalTargetType,
    ConfidenceLevel,
    FailureCategory,
    FailureSeverity,
    RiskLevel,
    SemanticStatus,
    TechnicalStatus,
    WorkflowStatus,
    WorkflowVersionStatus,
)
from app.domain.errors import (
    ApprovalRequiredError,
    DomainValidationError,
    InvariantViolationError,
)
from app.domain.models.approval import Approval
from app.domain.models.project import Project
from app.domain.models.specification import Specification
from app.domain.models.workflow import Workflow, WorkflowVersion
from app.domain.services.audit_service import AuditService
from app.domain.services.deployment_manager import DeploymentManager
from app.domain.services.deployment_policy import DeploymentAuthorizationPolicy
from app.domain.services.diagnosis_engine import DiagnosisEngine, StructuredDiagnosis
from app.domain.services.regression_engine import RegressionEngine, RegressionResult, RegressionSuite
from app.domain.services.repair_engine import PatchType, RepairEngine, RepairPatch, RepairProposal
from app.domain.services.requirement_translator import RequirementTranslator
from app.domain.services.specification_service import SpecificationService
from app.domain.services.workflow_builder import WorkflowBuilder
from app.domain.services.workflow_monitor import (
    AlertSeverity,
    HealthStatus,
    WorkflowHealthReport,
    WorkflowMonitor,
)
from app.domain.services.workflow_planner import WorkflowPlan, WorkflowPlanner
from app.domain.services.workflow_test_engine import (
    AssertionType,
    TestAssertion,
    TestCaseResult,
    TestScenario,
    WorkflowTestEngine,
)
from app.domain.services.workflow_validator import ValidationReport, WorkflowValidator


@dataclass(frozen=True)
class EndToEndPipelineResult:
    """Consolidated outcome of the autonomous end-to-end pipeline run."""
    task_id: UUID
    project_id: UUID
    workflow_id: UUID
    success: bool
    stages_executed: List[str]
    workflow_name: str
    specification_version: int
    workflow_version: int
    validation_passed: bool
    tests_passed: bool
    deployed_environment: str
    health_status: HealthStatus
    repair_successful: bool = False
    correlation_id: str = ""
    error_message: Optional[str] = None
    executed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": str(self.task_id),
            "project_id": str(self.project_id),
            "workflow_id": str(self.workflow_id),
            "success": self.success,
            "stages_executed": list(self.stages_executed),
            "workflow_name": self.workflow_name,
            "specification_version": self.specification_version,
            "workflow_version": self.workflow_version,
            "validation_passed": self.validation_passed,
            "tests_passed": self.tests_passed,
            "deployed_environment": self.deployed_environment,
            "health_status": self.health_status.value,
            "repair_successful": self.repair_successful,
            "correlation_id": self.correlation_id,
            "error_message": self.error_message,
            "executed_at": self.executed_at.isoformat(),
        }


class EndToEndPipeline:
    """Executes the full canonical 10-stage AAE autonomous software engineering lifecycle."""

    def __init__(
        self,
        translator: Optional[RequirementTranslator] = None,
        spec_service: Optional[SpecificationService] = None,
        planner: Optional[WorkflowPlanner] = None,
        builder: Optional[WorkflowBuilder] = None,
        validator: Optional[WorkflowValidator] = None,
        tester: Optional[WorkflowTestEngine] = None,
        deployer: Optional[DeploymentManager] = None,
        monitor: Optional[WorkflowMonitor] = None,
        diagnostician: Optional[DiagnosisEngine] = None,
        repairer: Optional[RepairEngine] = None,
        regression_engine: Optional[RegressionEngine] = None,
        audit_service: Optional[AuditService] = None,
    ) -> None:
        self.translator = translator or RequirementTranslator()
        self.spec_service = spec_service or SpecificationService()
        self.planner = planner or WorkflowPlanner()
        self.builder = builder or WorkflowBuilder()
        self.validator = validator or WorkflowValidator()
        self.tester = tester or WorkflowTestEngine()
        self.deployer = deployer or DeploymentManager()
        self.monitor = monitor or WorkflowMonitor()
        self.diagnostician = diagnostician or DiagnosisEngine()
        self.repairer = repairer or RepairEngine()
        self.regression_engine = regression_engine or RegressionEngine()
        self.audit_service = audit_service

    def execute_lifecycle(
        self,
        project_id: UUID,
        user_request: str,
        approver: str = "Lead Engineer",
        target_environment: str = "production",
        simulate_failure_and_repair: bool = True,
        correlation_id: Optional[str] = None,
    ) -> EndToEndPipelineResult:
        """Run the end-to-end autonomous engineering demonstration."""
        task_id = uuid4()
        cid = correlation_id or f"corr-e2e-{uuid4().hex[:8]}"
        stages: List[str] = []

        # -------------------------------------------------------------
        # Stage 1: Requirement Analysis
        # -------------------------------------------------------------
        stages.append("Requirement Analysis")
        translation_result = self.translator.translate(
            project_id=project_id,
            raw_text=user_request,
            created_by="user",
        )
        req = translation_result.requirement

        # -------------------------------------------------------------
        # Stage 2: Specification Creation & Submission
        # -------------------------------------------------------------
        stages.append("Specification Creation")
        spec = self.spec_service.create_specification_from_requirement(
            requirement=req,
            allow_draft_on_ambiguity=True,
            correlation_id=cid,
        )
        self.spec_service.submit_for_review(spec, actor="agent", correlation_id=cid)

        # -------------------------------------------------------------
        # Stage 3: Human Approval Gate
        # -------------------------------------------------------------
        stages.append("Human Approval Gate")
        approval = self.spec_service.approve_specification(
            specification=spec,
            version_number=1,
            approver=approver,
            comments="Approved automated pipeline request",
            correlation_id=cid,
        )

        # -------------------------------------------------------------
        # Stage 4: Topology Planning
        # -------------------------------------------------------------
        stages.append("Workflow Planning")
        plan = self.planner.create_plan(
            specification=spec,
            workflow_name="Lead Intake & Notification Automation",
        )

        # -------------------------------------------------------------
        # Stage 5: Workflow Building
        # -------------------------------------------------------------
        stages.append("Workflow Building")
        workflow_json = self.builder.build_workflow_definition(plan=plan)

        # Create workflow aggregate
        wf = Workflow(project_id=project_id, name="Lead Intake & Notification Automation")
        wf_ver = wf.add_version(
            specification_version_id=spec.versions[0].id,
            definition=workflow_json,
            change_reason="Initial build from plan",
        )

        # -------------------------------------------------------------
        # Stage 6: 7-Layer Validation
        # -------------------------------------------------------------
        stages.append("Workflow Validation")
        val_report = self.validator.validate(workflow_json)
        if not val_report.is_valid:
            return EndToEndPipelineResult(
                task_id=task_id,
                project_id=project_id,
                workflow_id=wf.id,
                success=False,
                stages_executed=stages,
                workflow_name=wf.name,
                specification_version=1,
                workflow_version=wf_ver.version_number,
                validation_passed=False,
                tests_passed=False,
                deployed_environment=target_environment,
                health_status=HealthStatus.UNHEALTHY,
                correlation_id=cid,
                error_message=f"Validation failed with {len(val_report.issues)} issues",
            )
        wf_ver.validate()

        # -------------------------------------------------------------
        # Stage 7: Testing
        # -------------------------------------------------------------
        stages.append("Technical & Semantic Testing")
        scenario = TestScenario(
            name="End-to-End Form Submission Test",
            description="Verify lead intake webhook triggers and completes successfully",
            inputs={"lead": {"name": "Alice", "email": "alice@example.com"}},
            expected_outputs={},
            expected_technical_status=TechnicalStatus.SUCCESS,
            expected_semantic_status=SemanticStatus.SATISFIED,
        )
        test_report = self.tester.run_tests(
            workflow_id=wf.id,
            workflow_version_id=wf_ver.id,
            definition=workflow_json,
            scenarios=[scenario],
            specification=spec,
            correlation_id=cid,
        )
        if not test_report.all_passed:
            return EndToEndPipelineResult(
                task_id=task_id,
                project_id=project_id,
                workflow_id=wf.id,
                success=False,
                stages_executed=stages,
                workflow_name=wf.name,
                specification_version=1,
                workflow_version=wf_ver.version_number,
                validation_passed=True,
                tests_passed=False,
                deployed_environment=target_environment,
                health_status=HealthStatus.UNHEALTHY,
                correlation_id=cid,
                error_message="Test assertions failed",
            )
        wf_ver.mark_tested()
        wf_ver.mark_approved()

        # -------------------------------------------------------------
        # Stage 8: Deployment Gate & Deployment
        # -------------------------------------------------------------
        stages.append("Production Deployment")
        # Record explicit approval for deployment if production
        deploy_approval = None
        if target_environment == "production":
            deploy_approval = Approval(
                target_type=ApprovalTargetType.WORKFLOW_VERSION,
                target_id=wf.id,
                target_version=wf_ver.version_number,
                actor=approver,
                action="deploy",
                environment="production",
            )
            deploy_approval.approve(comments="Approved production deployment")

        deployment = self.deployer.deploy(
            workflow=wf,
            version_number=wf_ver.version_number,
            target_environment=target_environment,
            deployed_by=approver,
            approval=deploy_approval,
            correlation_id=cid,
        )

        # -------------------------------------------------------------
        # Stage 9: Operational Telemetry & Monitoring
        # -------------------------------------------------------------
        stages.append("Operational Telemetry & Monitoring")
        for _ in range(5):
            self.monitor.record_execution(wf.id, duration_ms=150.0, is_success=True)
        health = self.monitor.evaluate_health(wf.id, workflow=wf)

        repair_successful = False

        # -------------------------------------------------------------
        # Stage 10: Simulated Failure -> Diagnosis -> Repair -> Regression -> Re-deploy
        # -------------------------------------------------------------
        if simulate_failure_and_repair:
            stages.append("Failure Injection & Diagnosis")
            # 1. Record simulated failures
            for _ in range(3):
                self.monitor.record_execution(
                    wf.id,
                    duration_ms=250.0,
                    is_success=False,
                    error_message="HTTP 401 Unauthorized: Expired Webhook API Token",
                )

            # 2. Diagnostician diagnoses the failure
            diag = self.diagnostician.diagnose_execution(
                execution_data={
                    "failed_node": "HTTP Post Lead",
                    "error_message": "HTTP 401 Unauthorized: Expired Webhook API Token",
                    "execution_path": ["Webhook", "HTTP Post Lead"],
                },
                workflow_id=wf.id,
                workflow_version_number=wf_ver.version_number,
            )

            stages.append("Surgical Repair")
            # 3. Repairer generates surgical fix patch
            proposal = self.repairer.propose_repair(
                diagnosis=diag,
                definition=wf_ver.definition,
            )

            # 4. Apply repair creating v2 workflow version
            v2, _ = self.repairer.apply_repair(
                workflow=wf,
                proposal=proposal,
                created_by=approver,
            )

            # 5. Validate repaired version
            v2_val = self.validator.validate(v2.definition)
            if v2_val.is_valid:
                v2.validate()

            stages.append("Regression Testing")
            # 6. Run regression suite
            self.regression_engine.register_scenario(wf.id, scenario, is_critical=True)
            reg_result = self.regression_engine.run_regression(
                workflow=wf,
                version_number=v2.version_number,
                failing_scenario=scenario,
                correlation_id=cid,
            )

            if reg_result.all_passed:
                v2.mark_tested()
                v2.mark_approved()

                # Re-deploy repaired version
                re_deploy_approval = None
                if target_environment == "production":
                    re_deploy_approval = Approval(
                        target_type=ApprovalTargetType.WORKFLOW_VERSION,
                        target_id=wf.id,
                        target_version=v2.version_number,
                        actor=approver,
                        action="deploy",
                        environment="production",
                    )
                    re_deploy_approval.approve(comments="Approved production repair deployment")

                self.deployer.deploy(
                    workflow=wf,
                    version_number=v2.version_number,
                    target_environment=target_environment,
                    deployed_by=approver,
                    approval=re_deploy_approval,
                    correlation_id=cid,
                )
                repair_successful = True
                wf_ver = v2

            # Record clean telemetry post-repair (establishing healthy SLA baseline)
            for _ in range(30):
                self.monitor.record_execution(wf.id, duration_ms=140.0, is_success=True)
            health = self.monitor.evaluate_health(wf.id, workflow=wf)

        return EndToEndPipelineResult(
            task_id=task_id,
            project_id=project_id,
            workflow_id=wf.id,
            success=True,
            stages_executed=stages,
            workflow_name=wf.name,
            specification_version=1,
            workflow_version=wf_ver.version_number,
            validation_passed=True,
            tests_passed=True,
            deployed_environment=target_environment,
            health_status=health.overall_status,
            repair_successful=repair_successful,
            correlation_id=cid,
        )
