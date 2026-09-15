"""Repairer Agent Component (Phase 15).

Agent interface for synthesizing surgical repair proposals, applying versioned repairs,
and safely rolling back failed revisions.
"""

from typing import Optional, Tuple
from uuid import UUID

from app.domain.models.repair import RepairAttempt
from app.domain.models.workflow import Workflow, WorkflowVersion
from app.domain.services.diagnosis_engine import StructuredDiagnosis
from app.domain.services.repair_engine import (
    RepairEngine,
    RepairProposal,
)
from app.domain.services.workflow_validator import (
    ValidationReport,
    WorkflowValidator,
)


class Repairer:
    """Agent component providing controlled, versioned repair of workflows."""

    def __init__(
        self,
        repair_engine: Optional[RepairEngine] = None,
        validator: Optional[WorkflowValidator] = None,
    ) -> None:
        self.engine = repair_engine or RepairEngine()
        self.validator = validator or WorkflowValidator()

    def propose(
        self,
        diagnosis: StructuredDiagnosis,
        workflow: Workflow,
    ) -> RepairProposal:
        """Synthesize repair proposal from a structured diagnosis."""
        cur_ver = workflow.get_current_version()
        definition = cur_ver.definition if cur_ver else {}
        return self.engine.propose_repair(diagnosis, definition)

    def repair(
        self,
        workflow: Workflow,
        proposal: RepairProposal,
        created_by: str = "agent.repairer",
        correlation_id: Optional[str] = None,
    ) -> Tuple[WorkflowVersion, RepairAttempt, ValidationReport]:
        """Apply repair proposal and immediately run validation on the new version."""
        new_version, attempt = self.engine.apply_repair(
            workflow=workflow,
            proposal=proposal,
            created_by=created_by,
            correlation_id=correlation_id,
        )

        validation_report = self.validator.validate(new_version.definition)

        # If repaired definition is valid, validate version status
        if validation_report.is_valid:
            new_version.validate()
        else:
            attempt.mark_rejected()

        return new_version, attempt, validation_report

    def rollback(
        self,
        workflow: Workflow,
        target_version_number: int,
        reason: str = "Rollback after repair attempt failure",
        actor: str = "agent.repairer",
        correlation_id: Optional[str] = None,
    ) -> WorkflowVersion:
        """Rollback to a previous stable workflow version."""
        return self.engine.rollback(
            workflow=workflow,
            target_version_number=target_version_number,
            reason=reason,
            actor=actor,
            correlation_id=correlation_id,
        )
