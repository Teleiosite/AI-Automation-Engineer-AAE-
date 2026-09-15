"""Workflow Validator Agent Component (Phase 12).

Agent interface for independent technical, security, and semantic validation
of candidate workflow definitions prior to execution or deployment.
"""

from typing import Any, Dict, Optional
from app.domain.models.specification import Specification
from app.domain.models.workflow import Workflow
from app.domain.services.workflow_planner import WorkflowPlan
from app.domain.services.workflow_validator import (
    ValidationReport,
    WorkflowValidator,
)


class Validator:
    """Agent component providing independent verification of workflows."""

    def __init__(self, validator_service: Optional[WorkflowValidator] = None) -> None:
        self.validator_service = validator_service or WorkflowValidator()

    def validate(
        self,
        definition: Dict[str, Any],
        specification: Optional[Specification] = None,
        plan: Optional[WorkflowPlan] = None,
    ) -> ValidationReport:
        """Validate candidate workflow definition dictionary."""
        return self.validator_service.validate(
            definition=definition,
            specification=specification,
            plan=plan,
        )

    def validate_workflow(
        self,
        workflow: Workflow,
        version_number: Optional[int] = None,
        specification: Optional[Specification] = None,
        plan: Optional[WorkflowPlan] = None,
    ) -> ValidationReport:
        """Validate workflow aggregate definition for current or specific version."""
        if version_number is not None:
            target_version = None
            for v in workflow.versions:
                if v.version_number == version_number:
                    target_version = v
                    break
            definition = target_version.definition if target_version else {}
        else:
            version = workflow.get_current_version()
            definition = version.definition if version else {}

        return self.validator_service.validate(
            definition=definition,
            specification=specification,
            plan=plan,
        )
