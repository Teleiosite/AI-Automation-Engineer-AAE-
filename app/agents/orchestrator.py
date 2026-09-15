"""Agent Orchestrator (Phase 9).

Coordinates the 21-state automation lifecycle across specialized agent components,
enforcing approval gates and deterministic loop protection.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID, uuid4

from app.domain.enums import AgentState, ApprovalDecision, ApprovalStatus, SpecificationStatus
from app.domain.errors import InvariantViolationError, InvalidStateTransitionError
from app.domain.models.approval import Approval
from app.domain.models.requirement import Requirement
from app.domain.models.specification import Specification
from app.domain.services.audit_service import AuditService
from app.domain.services.requirement_translator import RequirementTranslator, RequirementTranslationResult
from app.domain.services.specification_service import SpecificationService
from app.domain.state_machine import AgentStateMachine, AgentStateTransition


@dataclass
class AgentRunContext:
    """Stateful execution context for an active orchestrator task."""
    task_id: UUID
    project_id: UUID
    original_request: str
    state_machine: AgentStateMachine
    requirement: Optional[Requirement] = None
    specification: Optional[Specification] = None
    approval: Optional[Approval] = None
    repair_attempts: int = 0
    planning_attempts: int = 0
    clarification_attempts: int = 0
    errors: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def current_state(self) -> AgentState:
        return self.state_machine.current_state


class AgentOrchestrator:
    """Orchestrates the autonomous software engineering lifecycle.

    Maintains lifecycle state transitions, integrates specialized components,
    and enforces loop limits to prevent uncontrolled execution cycles.
    """

    def __init__(
        self,
        translator: RequirementTranslator,
        specification_service: SpecificationService,
        audit_service: Optional[AuditService] = None,
        max_repair_attempts: int = 3,
        max_planning_attempts: int = 3,
        max_clarification_attempts: int = 3,
        max_transitions: int = 50,
    ) -> None:
        self.translator = translator
        self.specification_service = specification_service
        self.audit_service = audit_service
        self.max_repair_attempts = max_repair_attempts
        self.max_planning_attempts = max_planning_attempts
        self.max_clarification_attempts = max_clarification_attempts
        self.max_transitions = max_transitions

    def start_task(
        self,
        project_id: UUID,
        raw_user_request: str,
        correlation_id: Optional[str] = None,
        actor: str = "user",
    ) -> AgentRunContext:
        """Initialize a new task at INTAKE, transition to ANALYSING, and translate requirement."""
        task_id = uuid4()
        sm = AgentStateMachine(task_id=task_id, initial_state=AgentState.INTAKE)
        context = AgentRunContext(
            task_id=task_id,
            project_id=project_id,
            original_request=raw_user_request,
            state_machine=sm,
        )

        self._record_transition(context, AgentState.ANALYSING, actor=actor, reason="Beginning requirement analysis", correlation_id=correlation_id)

        # Execute requirement translation
        result = self.translator.translate(
            project_id=project_id,
            raw_text=raw_user_request,
            created_by=actor,
        )
        context.requirement = result.requirement

        if result.is_clarification_required:
            self._record_transition(
                context,
                AgentState.CLARIFICATION_REQUIRED,
                actor="orchestrator",
                reason=f"Ambiguities or conflicts detected: {', '.join(result.clarification_questions[:3])}",
                correlation_id=correlation_id,
            )
            context.specification = self.specification_service.create_specification_from_requirement(
                requirement=result.requirement,
                allow_draft_on_ambiguity=True,
                correlation_id=correlation_id,
            )
        else:
            context.specification = self.specification_service.create_specification_from_requirement(
                requirement=result.requirement,
                allow_draft_on_ambiguity=False,
                correlation_id=correlation_id,
            )
            self._record_transition(
                context,
                AgentState.SPECIFICATION_READY,
                actor="orchestrator",
                reason="Specification created and ready for review",
                correlation_id=correlation_id,
            )

        return context

    def resolve_clarification(
        self,
        context: AgentRunContext,
        clarified_text: str,
        actor: str = "user",
        correlation_id: Optional[str] = None,
    ) -> AgentRunContext:
        """Incorporate user clarification and re-evaluate requirements."""
        if context.current_state != AgentState.CLARIFICATION_REQUIRED:
            raise InvariantViolationError(f"Cannot resolve clarification when in state '{context.current_state.value}'")

        context.clarification_attempts += 1
        if context.clarification_attempts > self.max_clarification_attempts:
            self._record_transition(
                context,
                AgentState.BLOCKED,
                actor="orchestrator",
                reason="Max clarification attempts exceeded; human escalation required",
                correlation_id=correlation_id,
            )
            return context

        self._record_transition(
            context,
            AgentState.ANALYSING,
            actor=actor,
            reason="Re-analysing with supplied user clarifications",
            correlation_id=correlation_id,
        )

        combined_text = f"{context.original_request}\nClarification: {clarified_text}"
        result = self.translator.translate(
            project_id=context.project_id,
            raw_text=combined_text,
            created_by=actor,
        )
        context.requirement = result.requirement

        if result.is_clarification_required:
            self._record_transition(
                context,
                AgentState.CLARIFICATION_REQUIRED,
                actor="orchestrator",
                reason="Remaining ambiguities require further clarification",
                correlation_id=correlation_id,
            )
        else:
            context.specification = self.specification_service.create_specification_from_requirement(
                requirement=result.requirement,
                allow_draft_on_ambiguity=False,
                correlation_id=correlation_id,
            )
            self._record_transition(
                context,
                AgentState.SPECIFICATION_READY,
                actor="orchestrator",
                reason="Clarifications resolved; specification ready",
                correlation_id=correlation_id,
            )

        return context

    def submit_specification_for_review(
        self,
        context: AgentRunContext,
        actor: str = "agent",
        correlation_id: Optional[str] = None,
    ) -> None:
        """Submit the generated specification for formal human review."""
        if not context.specification:
            raise InvariantViolationError("No specification present to submit for review")

        self.specification_service.submit_for_review(
            specification=context.specification,
            actor=actor,
            correlation_id=correlation_id,
        )

    def record_human_approval(
        self,
        context: AgentRunContext,
        version_number: int,
        approver: str,
        decision: str,
        comments: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> Optional[Approval]:
        """Record human governance decision on the specification."""
        if not context.specification:
            raise InvariantViolationError("No specification present for approval")

        normalized = decision.strip().upper()
        if normalized == "APPROVED":
            approval = self.specification_service.approve_specification(
                specification=context.specification,
                version_number=version_number,
                approver=approver,
                comments=comments,
                correlation_id=correlation_id,
            )
            context.approval = approval
            return approval
        elif normalized == "REJECTED":
            self.specification_service.reject_specification(
                specification=context.specification,
                rejecter=approver,
                reason=comments or "Rejected by human reviewer",
                correlation_id=correlation_id,
            )
            if context.state_machine.can_transition_to(AgentState.CANCELLED):
                self._record_transition(context, AgentState.CANCELLED, actor=approver, reason="Specification rejected by reviewer", correlation_id=correlation_id)
            elif context.state_machine.can_transition_to(AgentState.BLOCKED):
                self._record_transition(context, AgentState.BLOCKED, actor=approver, reason="Specification rejected by reviewer", correlation_id=correlation_id)
            return None
        else:
            raise ValueError(f"Unsupported approval decision: {decision}")

    def handle_execution_failure(
        self,
        context: AgentRunContext,
        error_message: str,
        correlation_id: Optional[str] = None,
    ) -> AgentState:
        """Process execution failure through DIAGNOSING -> REPAIRING with loop limits."""
        context.errors.append(error_message)

        # Transition to FAILED if allowed
        if context.state_machine.can_transition_to(AgentState.FAILED):
            self._record_transition(
                context,
                AgentState.FAILED,
                actor="orchestrator",
                reason=f"Execution failed: {error_message}",
                correlation_id=correlation_id,
            )

        # Transition to DIAGNOSING
        if context.state_machine.can_transition_to(AgentState.DIAGNOSING):
            self._record_transition(
                context,
                AgentState.DIAGNOSING,
                actor="orchestrator",
                reason="Diagnosing root cause of failure",
                correlation_id=correlation_id,
            )

        context.repair_attempts += 1

        # Loop protection: check max repair threshold (§39, §70)
        if context.repair_attempts > self.max_repair_attempts:
            self._record_transition(
                context,
                AgentState.FAILED_PERMANENTLY,
                actor="orchestrator",
                reason=f"Max repair attempts ({self.max_repair_attempts}) exceeded. Uncontrolled repair loop prevented.",
                correlation_id=correlation_id,
            )
            return context.current_state

        # Otherwise proceed to REPAIRING
        if context.state_machine.can_transition_to(AgentState.REPAIRING):
            self._record_transition(
                context,
                AgentState.REPAIRING,
                actor="orchestrator",
                reason=f"Attempting repair {context.repair_attempts}/{self.max_repair_attempts}",
                correlation_id=correlation_id,
            )

        return context.current_state

    def _record_transition(
        self,
        context: AgentRunContext,
        target_state: AgentState,
        actor: str,
        reason: str,
        correlation_id: Optional[str] = None,
    ) -> None:
        """Execute state transition, enforcing loop protection limits and audit logging."""
        if len(context.state_machine.transitions) >= self.max_transitions:
            if not context.state_machine.is_terminal():
                context.state_machine.transition_to(
                    AgentState.BLOCKED,
                    actor="orchestrator",
                    reason=f"Exceeded max allowed state transitions ({self.max_transitions})",
                    correlation_id=correlation_id,
                )
            return

        from_state = context.current_state
        context.state_machine.transition_to(
            target_state=target_state,
            actor=actor,
            reason=reason,
            correlation_id=correlation_id,
        )

        if self.audit_service:
            self.audit_service.record_workflow_mutation(
                mutation_type="state_transition",
                workflow_id=str(context.task_id),
                actor=actor,
                version_number=len(context.state_machine.transitions),
                before_state={"state": from_state.value},
                after_state={"state": target_state.value},
                change_reason=reason,
                correlation_id=correlation_id,
            )
