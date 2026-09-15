"""Workflow Planner Agent Component (Phase 10).

Agent interface for producing capability-verified workflow plans from approved specifications.
"""

from typing import Optional
from app.domain.models.specification import Specification
from app.domain.services.workflow_planner import WorkflowPlan, WorkflowPlanner


class Planner:
    """Agent component responsible for workflow architecture and node planning."""

    def __init__(self, planner_service: WorkflowPlanner) -> None:
        self.planner_service = planner_service

    def plan(
        self,
        specification: Specification,
        version_number: Optional[int] = None,
        workflow_name: Optional[str] = None,
        environment: str = "development",
    ) -> WorkflowPlan:
        """Derive an executable workflow topology plan from an approved specification."""
        return self.planner_service.create_plan(
            specification=specification,
            version_number=version_number,
            workflow_name=workflow_name,
            environment=environment,
        )
