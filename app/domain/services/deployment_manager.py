"""Deployment Manager Service (§17 AAE_AGENT_SPECIFICATION, §19 CODEX_IMPLEMENTATION_PLAN).

Coordinates controlled workflow deployments across development, staging, and production environments,
enforcing approval gates, environment promotion rules, provider execution, and atomic rollback.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from app.domain.enums import (
    AgentState,
    ApprovalTargetType,
    DeploymentStatus,
    WorkflowStatus,
    WorkflowVersionStatus,
)
from app.domain.errors import (
    ApprovalRequiredError,
    DomainValidationError,
    InvalidStateTransitionError,
    InvariantViolationError,
)
from app.domain.models.approval import Approval
from app.domain.models.deployment import Deployment
from app.domain.models.workflow import Workflow, WorkflowVersion
from app.domain.services.audit_service import AuditService
from app.domain.services.deployment_policy import DeploymentAuthorizationPolicy


class DeploymentManager:
    """Domain service managing workflow promotions, production approval gating, and rollback."""

    ALLOWED_ENVIRONMENTS = {"development", "staging", "production"}

    def __init__(
        self,
        audit_service: Optional[AuditService] = None,
        provider: Optional[Any] = None,
    ) -> None:
        self.audit_service = audit_service
        self.provider = provider

    def deploy(
        self,
        workflow: Workflow,
        version_number: int,
        target_environment: str = "development",
        deployed_by: str = "agent.deployer",
        approval: Optional[Approval] = None,
        agent_state: AgentState = AgentState.APPROVED,
        activate: bool = True,
        correlation_id: Optional[str] = None,
    ) -> Deployment:
        """Execute a controlled, gated deployment to the target environment."""
        env = target_environment.strip().lower()
        if env not in self.ALLOWED_ENVIRONMENTS:
            raise DomainValidationError(
                f"Invalid target environment '{target_environment}'. Must be one of: {sorted(self.ALLOWED_ENVIRONMENTS)}"
            )

        # Locate target workflow version
        target_version: Optional[WorkflowVersion] = None
        for v in workflow.versions:
            if v.version_number == version_number:
                target_version = v
                break

        if not target_version:
            raise InvariantViolationError(f"Target version {version_number} does not exist on workflow {workflow.id}")

        # Development environment promotion helper (allow tested versions to proceed)
        if env == "development" and target_version.status == WorkflowVersionStatus.TESTED:
            target_version.mark_approved()

        # Instantiate deployment entity
        deployment = Deployment(
            workflow_id=workflow.id,
            workflow_version_id=target_version.id,
            workflow_version_number=target_version.version_number,
            target_environment=env,
            deployed_by=deployed_by,
        )

        # Enforce strict approval gating for staging and production
        if env in ("production", "staging"):
            DeploymentAuthorizationPolicy.authorize_deployment(
                deployment=deployment,
                workflow=workflow,
                workflow_version=target_version,
                approval=approval,
                agent_state=agent_state,
            )
        else:
            # Development authorization
            if target_version.status != WorkflowVersionStatus.APPROVED:
                raise InvariantViolationError(
                    f"Workflow version must be in APPROVED or TESTED status to deploy to '{env}', currently '{target_version.status.value}'"
                )
            deployment.mark_in_progress()

        # Provider runtime deployment if provider is configured
        provider_workflow_id = None
        if self.provider:
            try:
                # Deploy to provider
                res = self.provider.create_workflow(
                    name=f"{workflow.name} [{env}]",
                    definition=target_version.definition,
                )
                provider_workflow_id = res.get("id")
                if activate and provider_workflow_id:
                    self.provider.activate_workflow(provider_workflow_id)
            except Exception as e:
                deployment.mark_failed(str(e))
                if self.audit_service:
                    self.audit_service.record_deployment_event(
                        deployment_id=str(deployment.id),
                        workflow_id=str(workflow.id),
                        version_number=version_number,
                        environment=env,
                        actor=deployed_by,
                        approval_id=approval.id if approval else None,
                        status="FAILED",
                        correlation_id=correlation_id,
                        details={"error": str(e)},
                    )
                raise

        # Complete aggregate promotions
        target_version.mark_deployed()
        workflow.environment = env
        if activate:
            workflow.activate()
        deployment.mark_deployed()

        # Record audit trail
        if self.audit_service:
            self.audit_service.record_deployment_event(
                deployment_id=str(deployment.id),
                workflow_id=str(workflow.id),
                version_number=version_number,
                environment=env,
                actor=deployed_by,
                approval_id=approval.id if approval else None,
                status="SUCCESS",
                correlation_id=correlation_id,
                details={
                    "activated": activate,
                    "provider_workflow_id": provider_workflow_id,
                },
            )

        return deployment

    def rollback_deployment(
        self,
        workflow: Workflow,
        active_deployment: Deployment,
        target_version_number: int,
        reason: str = "Rollback due to post-deployment verification failure",
        actor: str = "agent.deployer",
        correlation_id: Optional[str] = None,
    ) -> Deployment:
        """Rollback active deployment to a previously verified stable version."""
        if active_deployment.status != DeploymentStatus.DEPLOYED:
            raise InvariantViolationError(f"Cannot rollback deployment in status '{active_deployment.status.value}'")

        # Mark active deployment as rolled back
        active_deployment.mark_rolled_back()

        # Locate rollback version
        target_version: Optional[WorkflowVersion] = None
        for v in workflow.versions:
            if v.version_number == target_version_number:
                target_version = v
                break

        if not target_version:
            raise InvariantViolationError(f"Target rollback version {target_version_number} does not exist")

        # Ensure target version is in DEPLOYED status
        if target_version.status != WorkflowVersionStatus.DEPLOYED:
            if target_version.status != WorkflowVersionStatus.APPROVED:
                target_version.status = WorkflowVersionStatus.APPROVED
            target_version.mark_deployed()

        # Execute rollback deployment
        rollback_dep = Deployment(
            workflow_id=workflow.id,
            workflow_version_id=target_version.id,
            workflow_version_number=target_version.version_number,
            target_environment=active_deployment.target_environment,
            deployed_by=actor,
        )
        rollback_dep.mark_in_progress()

        if self.provider:
            res = self.provider.create_workflow(
                name=f"{workflow.name} [{active_deployment.target_environment}] (Rollback)",
                definition=target_version.definition,
            )
            pwid = res.get("id")
            if pwid:
                self.provider.activate_workflow(pwid)

        workflow.activate()
        rollback_dep.mark_deployed()

        if self.audit_service:
            self.audit_service.record_deployment_event(
                deployment_id=str(rollback_dep.id),
                workflow_id=str(workflow.id),
                version_number=target_version_number,
                environment=active_deployment.target_environment,
                actor=actor,
                approval_id=None,
                status="SUCCESS",
                correlation_id=correlation_id,
                details={
                    "rollback_from_deployment": str(active_deployment.id),
                    "reason": reason,
                },
            )

        return rollback_dep
