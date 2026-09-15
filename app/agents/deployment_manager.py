"""Deployment Manager Agent Component (Phase 17).

Agent interface for controlled promotion, approval-gated releases,
and atomic deployment rollbacks.
"""

from typing import Any, Optional
from uuid import UUID

from app.domain.enums import AgentState
from app.domain.models.approval import Approval
from app.domain.models.deployment import Deployment
from app.domain.models.workflow import Workflow
from app.domain.services.deployment_manager import DeploymentManager


class DeploymentManagerAgent:
    """Agent component responsible for workflow deployment and environment promotions."""

    def __init__(self, deployment_manager: Optional[DeploymentManager] = None) -> None:
        self.manager = deployment_manager or DeploymentManager()

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
        """Promote and deploy workflow version to target environment."""
        return self.manager.deploy(
            workflow=workflow,
            version_number=version_number,
            target_environment=target_environment,
            deployed_by=deployed_by,
            approval=approval,
            agent_state=agent_state,
            activate=activate,
            correlation_id=correlation_id,
        )

    def rollback(
        self,
        workflow: Workflow,
        active_deployment: Deployment,
        target_version_number: int,
        reason: str = "Rollback requested",
        actor: str = "agent.deployer",
        correlation_id: Optional[str] = None,
    ) -> Deployment:
        """Rollback active deployment to historical version."""
        return self.manager.rollback_deployment(
            workflow=workflow,
            active_deployment=active_deployment,
            target_version_number=target_version_number,
            reason=reason,
            actor=actor,
            correlation_id=correlation_id,
        )
