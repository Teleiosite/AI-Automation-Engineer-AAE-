"""Workflow Builder Agent Component (Phase 11).

Agent interface for compiling workflow plans into n8n workflow definitions.
"""

from typing import Optional, Tuple
from uuid import UUID
from app.domain.models.workflow import Workflow, WorkflowVersion
from app.domain.services.workflow_builder import WorkflowBuilder
from app.domain.services.workflow_planner import WorkflowPlan


class Builder:
    """Agent component responsible for compiling workflow plans into concrete definitions."""

    def __init__(self, builder_service: WorkflowBuilder) -> None:
        self.builder_service = builder_service

    def build(
        self,
        plan: WorkflowPlan,
        project_id: UUID,
        created_by: str = "agent",
        workflow: Optional[Workflow] = None,
        correlation_id: Optional[str] = None,
    ) -> Tuple[Workflow, WorkflowVersion]:
        """Compile a plan into an n8n workflow aggregate and version."""
        return self.builder_service.build_workflow(
            plan=plan,
            project_id=project_id,
            created_by=created_by,
            workflow=workflow,
            correlation_id=correlation_id,
        )
