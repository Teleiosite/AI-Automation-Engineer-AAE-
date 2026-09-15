"""AAE Database ORM models registry."""

from app.db.models.project import ProjectModel
from app.db.models.requirement import RequirementItemModel, RequirementModel
from app.db.models.specification import SpecificationModel, SpecificationVersionModel
from app.db.models.workflow import WorkflowModel, WorkflowVersionModel
from app.db.models.execution import ExecutionModel
from app.db.models.approval import ApprovalModel
from app.db.models.deployment import DeploymentModel
from app.db.models.diagnostic import DiagnosticFindingModel, FailureRecordModel
from app.db.models.repair import RepairAttemptModel
from app.db.models.audit import AuditEventModel

__all__ = [
    "ProjectModel",
    "RequirementModel",
    "RequirementItemModel",
    "SpecificationModel",
    "SpecificationVersionModel",
    "WorkflowModel",
    "WorkflowVersionModel",
    "ExecutionModel",
    "ApprovalModel",
    "DeploymentModel",
    "FailureRecordModel",
    "DiagnosticFindingModel",
    "RepairAttemptModel",
    "AuditEventModel",
]
