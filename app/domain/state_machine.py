"""Deterministic 21-state Agent State Machine implementing AAE lifecycle."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set
from uuid import UUID, uuid4
from app.domain.enums import AgentState
from app.domain.errors import InvalidStateTransitionError


@dataclass(frozen=True)
class AgentStateTransition:
    """Immutable audit record of a lifecycle state transition."""
    from_state: AgentState
    to_state: AgentState
    actor: str
    reason: str
    correlation_id: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class AgentStateMachine:
    """
    Deterministic Agent State Machine enforcing the 21-state AAE lifecycle.
    Prevents shortcuts, protects governance gates, and fails closed in terminal states.
    """

    TERMINAL_STATES: Set[AgentState] = {
        AgentState.COMPLETED,
        AgentState.BLOCKED,
        AgentState.CANCELLED,
        AgentState.FAILED_PERMANENTLY,
    }

    # Strict transition matrix derived from AAE_AGENT_SPECIFICATION.md §4-5
    TRANSITION_MAP: Dict[AgentState, Set[AgentState]] = {
        AgentState.INTAKE: {
            AgentState.ANALYSING,
            AgentState.CANCELLED,
        },
        AgentState.ANALYSING: {
            AgentState.SPECIFICATION_READY,
            AgentState.CLARIFICATION_REQUIRED,
            AgentState.BLOCKED,
            AgentState.CANCELLED,
        },
        AgentState.CLARIFICATION_REQUIRED: {
            AgentState.ANALYSING,
            AgentState.BLOCKED,
            AgentState.CANCELLED,
        },
        AgentState.SPECIFICATION_READY: {
            AgentState.PLANNING,
            AgentState.CLARIFICATION_REQUIRED,
            AgentState.COMPLETED,  # Allowed if request was analysis/spec only
            AgentState.CANCELLED,
        },
        AgentState.PLANNING: {
            AgentState.BUILDING,
            AgentState.CLARIFICATION_REQUIRED,
            AgentState.BLOCKED,
            AgentState.CANCELLED,
        },
        AgentState.BUILDING: {
            AgentState.VALIDATING,
            AgentState.FAILED,
            AgentState.BLOCKED,
            AgentState.CANCELLED,
        },
        AgentState.VALIDATING: {
            AgentState.TESTING,
            AgentState.FAILED,
            AgentState.BLOCKED,
            AgentState.CANCELLED,
        },
        AgentState.TESTING: {
            AgentState.READY_FOR_APPROVAL,
            AgentState.FAILED,
            AgentState.BLOCKED,
            AgentState.CANCELLED,
        },
        AgentState.FAILED: {
            AgentState.DIAGNOSING,
            AgentState.BLOCKED,
            AgentState.FAILED_PERMANENTLY,
            AgentState.CANCELLED,
        },
        AgentState.DIAGNOSING: {
            AgentState.REPAIRING,
            AgentState.BLOCKED,
            AgentState.FAILED_PERMANENTLY,
            AgentState.CANCELLED,
        },
        AgentState.REPAIRING: {
            AgentState.VALIDATING,
            AgentState.RETESTING,
            AgentState.FAILED,
            AgentState.BLOCKED,
            AgentState.CANCELLED,
        },
        AgentState.RETESTING: {
            AgentState.READY_FOR_APPROVAL,
            AgentState.FAILED,
            AgentState.BLOCKED,
            AgentState.CANCELLED,
        },
        AgentState.READY_FOR_APPROVAL: {
            AgentState.APPROVED,
            AgentState.CLARIFICATION_REQUIRED,
            AgentState.BLOCKED,
            AgentState.CANCELLED,
        },
        AgentState.APPROVED: {
            AgentState.DEPLOYING,
            AgentState.BLOCKED,
            AgentState.CANCELLED,
        },
        AgentState.DEPLOYING: {
            AgentState.DEPLOYED,
            AgentState.FAILED,
            AgentState.BLOCKED,
        },
        AgentState.DEPLOYED: {
            AgentState.MONITORING,
            AgentState.COMPLETED,
            AgentState.FAILED,
        },
        AgentState.MONITORING: {
            AgentState.COMPLETED,
            AgentState.DIAGNOSING,
            AgentState.FAILED,
            AgentState.BLOCKED,
        },
        # Terminal states have no outbound transitions
        AgentState.COMPLETED: set(),
        AgentState.BLOCKED: set(),
        AgentState.CANCELLED: set(),
        AgentState.FAILED_PERMANENTLY: set(),
    }

    def __init__(
        self,
        task_id: Optional[UUID] = None,
        initial_state: AgentState = AgentState.INTAKE,
    ) -> None:
        self.task_id: UUID = task_id or uuid4()
        self.current_state: AgentState = initial_state
        self.transitions: List[AgentStateTransition] = []

    def is_terminal(self) -> bool:
        """Check if machine is in a terminal state."""
        return self.current_state in self.TERMINAL_STATES

    def can_transition_to(self, target_state: AgentState) -> bool:
        """Check whether a transition to target_state is permitted."""
        if self.is_terminal():
            return False
        allowed = self.TRANSITION_MAP.get(self.current_state, set())
        return target_state in allowed

    def transition_to(
        self,
        target_state: AgentState,
        actor: str = "agent",
        reason: str = "",
        correlation_id: Optional[str] = None,
    ) -> AgentStateTransition:
        """
        Execute a deterministic lifecycle transition.
        Raises InvalidStateTransitionError if the transition is prohibited.
        """
        if self.is_terminal():
            raise InvalidStateTransitionError(
                from_state=self.current_state.value,
                to_state=target_state.value,
                message=f"Cannot transition out of terminal state '{self.current_state.value}'",
            )

        if not self.can_transition_to(target_state):
            raise InvalidStateTransitionError(
                from_state=self.current_state.value,
                to_state=target_state.value,
                message=f"Forbidden transition from '{self.current_state.value}' to '{target_state.value}'",
            )

        transition = AgentStateTransition(
            from_state=self.current_state,
            to_state=target_state,
            actor=actor,
            reason=reason,
            correlation_id=correlation_id,
        )
        self.transitions.append(transition)
        self.current_state = target_state
        return transition
