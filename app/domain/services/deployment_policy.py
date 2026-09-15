"""Domain service for coordinating deployment authorization and governance gates."""

from typing import Optional
from app.domain.enums import AgentState, ApprovalTargetType, WorkflowVersionStatus
from app.domain.errors import (
    ApprovalRequiredError,
    InvalidStateTransitionError,
    InvariantViolationError,
    StaleApprovalError,
)
from app.domain.models.approval import Approval
from app.domain.models.deployment import Deployment
from app.domain.models.workflow import Workflow, WorkflowVersion


class DeploymentAuthorizationPolicy:
    """
    Stateless domain service that coordinates cross-aggregate deployment authorization.
    Verifies that AgentState is APPROVED, matching active Approval exists, version matches,
    and consumes the approval to prevent replay attacks.
    """

    @staticmethod
    def authorize_deployment(
        deployment: Deployment,
        workflow: Workflow,
        workflow_version: WorkflowVersion,
        approval: Optional[Approval],
        agent_state: AgentState,
    ) -> None:
        """
        Authorize and begin deployment under strict policy gating.
        Raises DomainError subclass if any governance requirement is violated.
        """
        # 1. State machine governance check
        if agent_state != AgentState.APPROVED:
            raise InvalidStateTransitionError(
                from_state=agent_state.value,
                to_state=AgentState.DEPLOYING.value,
                message=f"Agent must be in '{AgentState.APPROVED.value}' state before deploying, currently '{agent_state.value}'",
            )

        # 2. Approval presence check
        if not approval:
            raise ApprovalRequiredError(
                f"Deployment of workflow '{workflow.name}' to '{deployment.target_environment}' requires explicit approval"
            )

        # 3. Approval validity and target matching check
        is_valid = approval.is_valid_for(
            target_type=ApprovalTargetType.WORKFLOW_VERSION,
            target_id=workflow.id,
            target_version=workflow_version.version_number,
            environment=deployment.target_environment,
            action="deploy",
        )
        if not is_valid:
            raise StaleApprovalError(
                f"Approval '{approval.id}' is invalid, expired, revoked, or does not match "
                f"target workflow '{workflow.id}' version '{workflow_version.version_number}' for environment '{deployment.target_environment}'"
            )

        # 4. Version maturity check
        if workflow_version.status != WorkflowVersionStatus.APPROVED:
            raise InvariantViolationError(
                f"Workflow version must be in APPROVED status, currently '{workflow_version.status.value}'"
            )

        # 5. Version identity check
        if workflow_version.id != deployment.workflow_version_id:
            raise InvariantViolationError("Deployment workflow_version_id does not match target WorkflowVersion")

        # 6. Single-use consumption to prevent replay attacks
        approval.consume(action_id=deployment.id)
        deployment.approval_id = approval.id

        # 7. Transition deployment to in-progress
        deployment.mark_in_progress()
