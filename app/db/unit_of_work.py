"""Unit of Work pattern managing transactions, repository access, and atomic governance operations."""

from types import TracebackType
from typing import Optional, Type
from uuid import UUID
from sqlalchemy.orm import Session, sessionmaker
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
from app.db.session import SessionLocal
from app.domain.enums import AgentState
from app.domain.errors import InvariantViolationError
from app.domain.models.deployment import Deployment
from app.domain.services.deployment_policy import DeploymentAuthorizationPolicy


class UnitOfWork:
    """
    Context manager defining explicit transactional boundaries.
    Coordinating repositories, atomic commits, rollbacks, and governance operations.
    """

    def __init__(self, session_factory: Optional[sessionmaker] = None) -> None:
        self._session_factory = session_factory or SessionLocal
        self.session: Optional[Session] = None

        # Repositories (bound during active session)
        self.projects: Optional[ProjectRepository] = None
        self.requirements: Optional[RequirementRepository] = None
        self.specifications: Optional[SpecificationRepository] = None
        self.workflows: Optional[WorkflowRepository] = None
        self.executions: Optional[ExecutionRepository] = None
        self.approvals: Optional[ApprovalRepository] = None
        self.deployments: Optional[DeploymentRepository] = None
        self.diagnostics: Optional[DiagnosticRepository] = None
        self.repairs: Optional[RepairRepository] = None
        self.audits: Optional[AuditRepository] = None

    def __enter__(self) -> "UnitOfWork":
        self.session = self._session_factory()
        self.projects = ProjectRepository(self.session)
        self.requirements = RequirementRepository(self.session)
        self.specifications = SpecificationRepository(self.session)
        self.workflows = WorkflowRepository(self.session)
        self.executions = ExecutionRepository(self.session)
        self.approvals = ApprovalRepository(self.session)
        self.deployments = DeploymentRepository(self.session)
        self.diagnostics = DiagnosticRepository(self.session)
        self.repairs = RepairRepository(self.session)
        self.audits = AuditRepository(self.session)
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        if self.session is not None:
            if exc_type is not None:
                self.rollback()
            self.session.close()
            self.session = None

    def commit(self) -> None:
        """Commit current database transaction."""
        if self.session is not None:
            self.session.commit()

    def rollback(self) -> None:
        """Rollback current database transaction."""
        if self.session is not None:
            self.session.rollback()

    def authorize_and_create_deployment(
        self,
        workflow_id: UUID,
        workflow_version_number: int,
        approval_id: UUID,
        agent_state: AgentState,
        target_environment: str,
        deployed_by: str,
    ) -> Deployment:
        """
        Execute atomic deployment authorization within a single transaction boundary:
        1. Load workflow, version, and approval.
        2. Run DeploymentAuthorizationPolicy.authorize_deployment().
        3. Atomically consume approval via conditional SQL update (single-winner).
        4. Create and persist deployment record.
        Rolls back automatically on failure, preserving approval state.
        """
        assert self.workflows is not None
        assert self.approvals is not None
        assert self.deployments is not None

        # 1. Load domain entities
        workflow = self.workflows.get(workflow_id)
        if not workflow:
            raise InvariantViolationError(f"Workflow '{workflow_id}' does not exist")

        version = self.workflows.get_version(workflow_id, workflow_version_number)
        if not version:
            raise InvariantViolationError(
                f"Workflow version '{workflow_version_number}' does not exist for workflow '{workflow_id}'"
            )

        approval = self.approvals.get(approval_id)
        if not approval:
            raise InvariantViolationError(f"Approval '{approval_id}' does not exist")

        # 2. Construct draft deployment record
        deployment = Deployment(
            workflow_id=workflow.id,
            workflow_version_id=version.id,
            workflow_version_number=version.version_number,
            target_environment=target_environment,
            deployed_by=deployed_by,
        )

        # 3. Authorize via domain policy (verifies state == APPROVED, target match, env match)
        DeploymentAuthorizationPolicy.authorize_deployment(
            deployment=deployment,
            workflow=workflow,
            workflow_version=version,
            approval=approval,
            agent_state=agent_state,
        )

        # 4. Atomic database consumption (conditional UPDATE WHERE status = 'ACTIVE')
        self.approvals.consume_atomic(approval_id=approval.id, action_id=deployment.id)

        # 5. Persist deployment record
        persisted_deployment = self.deployments.save(deployment)

        return persisted_deployment
