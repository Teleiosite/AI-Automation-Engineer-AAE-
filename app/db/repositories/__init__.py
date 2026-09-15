"""AAE Repositories registry."""

from app.db.repositories.project_repo import ProjectRepository
from app.db.repositories.requirement_repo import RequirementRepository
from app.db.repositories.specification_repo import SpecificationRepository
from app.db.repositories.workflow_repo import WorkflowRepository
from app.db.repositories.execution_repo import ExecutionRepository
from app.db.repositories.approval_repo import ApprovalRepository
from app.db.repositories.deployment_repo import DeploymentRepository
from app.db.repositories.diagnostic_repo import DiagnosticRepository
from app.db.repositories.repair_repo import RepairRepository
from app.db.repositories.audit_repo import AuditRepository

__all__ = [
    "ProjectRepository",
    "RequirementRepository",
    "SpecificationRepository",
    "WorkflowRepository",
    "ExecutionRepository",
    "ApprovalRepository",
    "DeploymentRepository",
    "DiagnosticRepository",
    "RepairRepository",
    "AuditRepository",
]
