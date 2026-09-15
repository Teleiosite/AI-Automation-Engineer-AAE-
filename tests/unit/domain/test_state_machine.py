"""Unit tests for the 21-state Agent State Machine."""

import pytest
from app.domain.enums import AgentState
from app.domain.errors import InvalidStateTransitionError
from app.domain.state_machine import AgentStateMachine


def test_state_machine_happy_path():
    sm = AgentStateMachine()
    assert sm.current_state == AgentState.INTAKE
    assert not sm.is_terminal()

    # Walk through full 17-state lifecycle
    sm.transition_to(AgentState.ANALYSING, reason="Starting analysis")
    sm.transition_to(AgentState.SPECIFICATION_READY, reason="Spec compiled")
    sm.transition_to(AgentState.PLANNING, reason="Spec approved for planning")
    sm.transition_to(AgentState.BUILDING, reason="Plan complete")
    sm.transition_to(AgentState.VALIDATING, reason="Workflow nodes generated")
    sm.transition_to(AgentState.TESTING, reason="Validation passed")
    sm.transition_to(AgentState.READY_FOR_APPROVAL, reason="Tests passed")
    sm.transition_to(AgentState.APPROVED, reason="Human approved release")
    sm.transition_to(AgentState.DEPLOYING, reason="Deploying to staging")
    sm.transition_to(AgentState.DEPLOYED, reason="Activation verified")
    sm.transition_to(AgentState.MONITORING, reason="Observing signals")
    sm.transition_to(AgentState.COMPLETED, reason="Task complete")

    assert sm.current_state == AgentState.COMPLETED
    assert sm.is_terminal()
    assert len(sm.transitions) == 12


def test_clarification_loop():
    sm = AgentStateMachine()
    sm.transition_to(AgentState.ANALYSING)
    sm.transition_to(AgentState.CLARIFICATION_REQUIRED, reason="Missing webhook URL")
    assert sm.current_state == AgentState.CLARIFICATION_REQUIRED

    sm.transition_to(AgentState.ANALYSING, reason="User supplied URL")
    sm.transition_to(AgentState.SPECIFICATION_READY)
    assert sm.current_state == AgentState.SPECIFICATION_READY


def test_failure_diagnosis_and_repair_loop():
    sm = AgentStateMachine()
    sm.transition_to(AgentState.ANALYSING)
    sm.transition_to(AgentState.SPECIFICATION_READY)
    sm.transition_to(AgentState.PLANNING)
    sm.transition_to(AgentState.BUILDING)
    sm.transition_to(AgentState.VALIDATING)
    sm.transition_to(AgentState.TESTING)

    # Test fails
    sm.transition_to(AgentState.FAILED, reason="HTTP 401 in test")
    sm.transition_to(AgentState.DIAGNOSING, reason="Inspecting execution error")
    sm.transition_to(AgentState.REPAIRING, reason="Applying credential fix")
    sm.transition_to(AgentState.RETESTING, reason="Retesting credential fix")
    sm.transition_to(AgentState.READY_FOR_APPROVAL, reason="Retest passed")
    assert sm.current_state == AgentState.READY_FOR_APPROVAL


def test_analysis_only_task_completes_from_specification_ready():
    sm = AgentStateMachine()
    sm.transition_to(AgentState.ANALYSING)
    sm.transition_to(AgentState.SPECIFICATION_READY)
    # Analysis-only task transitions directly to COMPLETED
    sm.transition_to(AgentState.COMPLETED, reason="Analysis-only request completed")
    assert sm.is_terminal()


@pytest.mark.parametrize(
    "from_state, forbidden_to_state",
    [
        (AgentState.INTAKE, AgentState.DEPLOYED),
        (AgentState.INTAKE, AgentState.DEPLOYING),
        (AgentState.INTAKE, AgentState.BUILDING),
        (AgentState.INTAKE, AgentState.MONITORING),
        (AgentState.ANALYSING, AgentState.DEPLOYED),
        (AgentState.ANALYSING, AgentState.BUILDING),
        (AgentState.BUILDING, AgentState.DEPLOYED),
        (AgentState.BUILDING, AgentState.APPROVED),
        (AgentState.VALIDATING, AgentState.DEPLOYED),
        (AgentState.TESTING, AgentState.DEPLOYED),
        (AgentState.TESTING, AgentState.APPROVED),
        (AgentState.READY_FOR_APPROVAL, AgentState.DEPLOYED),
        (AgentState.READY_FOR_APPROVAL, AgentState.BUILDING),
        (AgentState.FAILED, AgentState.DEPLOYED),
        (AgentState.FAILED, AgentState.APPROVED),
        (AgentState.DIAGNOSING, AgentState.DEPLOYED),
        (AgentState.APPROVED, AgentState.DEPLOYED),  # Must transition through DEPLOYING
    ],
)
def test_forbidden_transitions_rejected(from_state, forbidden_to_state):
    sm = AgentStateMachine(initial_state=from_state)
    assert not sm.can_transition_to(forbidden_to_state)
    with pytest.raises(InvalidStateTransitionError):
        sm.transition_to(forbidden_to_state)


@pytest.mark.parametrize(
    "terminal_state",
    [
        AgentState.COMPLETED,
        AgentState.BLOCKED,
        AgentState.CANCELLED,
        AgentState.FAILED_PERMANENTLY,
    ],
)
def test_terminal_states_reject_all_outbound_transitions(terminal_state):
    sm = AgentStateMachine(initial_state=terminal_state)
    assert sm.is_terminal()
    for state in AgentState:
        assert not sm.can_transition_to(state)
        with pytest.raises(InvalidStateTransitionError):
            sm.transition_to(state)
