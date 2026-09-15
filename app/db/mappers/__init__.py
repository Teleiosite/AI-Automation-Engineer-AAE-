"""Domain <-> Persistence mappers registry."""

from app.db.mappers.project_mapper import project_to_domain, project_to_model
from app.db.mappers.requirement_mapper import (
    requirement_item_to_domain,
    requirement_item_to_model,
    requirement_to_domain,
    requirement_to_model,
)
from app.db.mappers.specification_mapper import (
    specification_to_domain,
    specification_to_model,
    specification_version_to_domain,
    specification_version_to_model,
)
from app.db.mappers.workflow_mapper import (
    workflow_to_domain,
    workflow_to_model,
    workflow_version_to_domain,
    workflow_version_to_model,
)
from app.db.mappers.execution_mapper import (
    execution_result_to_domain,
    execution_to_domain,
    execution_to_model,
)
from app.db.mappers.approval_mapper import approval_to_domain, approval_to_model
from app.db.mappers.deployment_mapper import deployment_to_domain, deployment_to_model
from app.db.mappers.diagnostic_mapper import (
    diagnostic_finding_to_domain,
    diagnostic_finding_to_model,
    failure_record_to_domain,
    failure_record_to_model,
)
from app.db.mappers.repair_mapper import repair_attempt_to_domain, repair_attempt_to_model
from app.db.mappers.audit_mapper import audit_event_to_domain, audit_event_to_model

__all__ = [
    "project_to_domain",
    "project_to_model",
    "requirement_to_domain",
    "requirement_to_model",
    "requirement_item_to_domain",
    "requirement_item_to_model",
    "specification_to_domain",
    "specification_to_model",
    "specification_version_to_domain",
    "specification_version_to_model",
    "workflow_to_domain",
    "workflow_to_model",
    "workflow_version_to_domain",
    "workflow_version_to_model",
    "execution_to_domain",
    "execution_to_model",
    "execution_result_to_domain",
    "approval_to_domain",
    "approval_to_model",
    "deployment_to_domain",
    "deployment_to_model",
    "failure_record_to_domain",
    "failure_record_to_model",
    "diagnostic_finding_to_domain",
    "diagnostic_finding_to_model",
    "repair_attempt_to_domain",
    "repair_attempt_to_model",
    "audit_event_to_domain",
    "audit_event_to_model",
]
