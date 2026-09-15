"""Unit tests for AgentOrchestrator and deterministic loop protection (Phase 9)."""

from uuid import uuid4
import pytest

from app.domain.enums import AgentState, ApprovalDecision, SpecificationStatus
from app.domain.services.audit_service import AuditService
from app.domain.services.requirement_translator import RequirementTranslator
from app.domain.services.specification_service import SpecificationService
from app.domain.state_machine import AgentStateMachine
from app.agents.orchestrator import AgentOrchestrator, AgentRunContext


@pytest.fixture
def recorded_events():
    events = []
    def sink(event):
        events.append(event)
    return events, sink


@pytest.fixture
def audit_service(recorded_events):
    _, sink = recorded_events
    return AuditService(sink=sink)


@pytest.fixture
def orchestrator(audit_service) -> AgentOrchestrator:
    translator = RequirementTranslator()
    spec_service = SpecificationService(audit_service=audit_service)
    return AgentOrchestrator(
        translator=translator,
        specification_service=spec_service,
        audit_service=audit_service,
        max_repair_attempts=3,
        max_clarification_attempts=2,
    )


# 1. Happy Path: Intake -> Analysing -> Specification Ready
def test_orchestrator_happy_path(orchestrator):
    project_id = uuid4()
    req_text = (
        "Whenever somebody submits our website contact form, "
        "save their information in PostgreSQL leads_table and send them "
        "a WhatsApp message confirming that we received their enquiry."
    )

    context = orchestrator.start_task(project_id, req_text)

    assert context.current_state == AgentState.SPECIFICATION_READY
    assert context.requirement is not None
    assert context.specification is not None
    assert context.specification.status == SpecificationStatus.DRAFT
    assert len(context.state_machine.transitions) == 2  # INTAKE -> ANALYSING -> SPECIFICATION_READY


# 2. Clarification Loop: Missing Trigger -> Clarification -> Spec Ready
def test_orchestrator_clarification_loop(orchestrator):
    project_id = uuid4()
    vague_text = "Format customer addresses and write to PostgreSQL."

    context = orchestrator.start_task(project_id, vague_text)

    assert context.current_state == AgentState.CLARIFICATION_REQUIRED
    assert context.specification.status == SpecificationStatus.CLARIFICATION_REQUIRED

    # Provide clarification
    clarified_context = orchestrator.resolve_clarification(
        context,
        clarified_text="Trigger on webhook POST /api/leads and write to customers table.",
    )

    assert clarified_context.current_state == AgentState.SPECIFICATION_READY
    assert clarified_context.specification.status == SpecificationStatus.DRAFT


# 3. Clarification Loop Protection: Exceeding max attempts transitions to BLOCKED
def test_orchestrator_max_clarification_loop_protection(orchestrator):
    project_id = uuid4()
    vague_text = "Do some automation."

    context = orchestrator.start_task(project_id, vague_text)
    assert context.current_state == AgentState.CLARIFICATION_REQUIRED

    # Attempt 1 (still vague)
    orchestrator.resolve_clarification(context, "still vague text")
    assert context.current_state == AgentState.CLARIFICATION_REQUIRED

    # Attempt 2 (still vague)
    orchestrator.resolve_clarification(context, "another vague text")
    assert context.current_state == AgentState.CLARIFICATION_REQUIRED

    # Attempt 3 (exceeds max_clarification_attempts=2 -> BLOCKED)
    orchestrator.resolve_clarification(context, "yet another vague text")
    assert context.current_state == AgentState.BLOCKED
    assert context.state_machine.is_terminal() is True


# 4. Repair Loop Protection: Exceeding max repair attempts transitions to FAILED_PERMANENTLY
def test_orchestrator_max_repair_loop_protection(orchestrator):
    project_id = uuid4()
    context = AgentRunContext(
        task_id=uuid4(),
        project_id=project_id,
        original_request="Test",
        state_machine=AgentStateMachine(initial_state=AgentState.BUILDING),
    )

    # Transition to TESTING
    context.state_machine.transition_to(AgentState.VALIDATING)
    context.state_machine.transition_to(AgentState.TESTING)

    # Failure 1
    state1 = orchestrator.handle_execution_failure(context, "Connection timeout to PostgreSQL")
    assert state1 == AgentState.REPAIRING
    assert context.repair_attempts == 1

    # Transition to RETESTING then fail again
    context.state_machine.transition_to(AgentState.RETESTING)
    state2 = orchestrator.handle_execution_failure(context, "Syntax error in SQL node")
    assert state2 == AgentState.REPAIRING
    assert context.repair_attempts == 2

    # Transition to RETESTING then fail again
    context.state_machine.transition_to(AgentState.RETESTING)
    state3 = orchestrator.handle_execution_failure(context, "Authentication failed")
    assert state3 == AgentState.REPAIRING
    assert context.repair_attempts == 3

    # Transition to RETESTING then fail 4th time (exceeds max_repair_attempts=3)
    context.state_machine.transition_to(AgentState.RETESTING)
    state4 = orchestrator.handle_execution_failure(context, "Persistent database crash")
    assert state4 == AgentState.FAILED_PERMANENTLY
    assert context.current_state == AgentState.FAILED_PERMANENTLY
    assert context.state_machine.is_terminal() is True


# 5. Human Approval Gate Integration
def test_orchestrator_human_approval_gate(orchestrator):
    project_id = uuid4()
    req_text = "Every Monday at 8:00 AM, send an email report from PostgreSQL customers table."

    context = orchestrator.start_task(project_id, req_text)
    assert context.current_state == AgentState.SPECIFICATION_READY

    # Submit for review
    orchestrator.submit_specification_for_review(context)
    assert context.specification.status == SpecificationStatus.READY_FOR_REVIEW

    # Approve
    approval = orchestrator.record_human_approval(
        context,
        version_number=1,
        approver="lead_architect_sarah",
        decision="APPROVED",
        comments="Approved for development",
    )

    assert approval is not None
    assert approval.decision == ApprovalDecision.APPROVED
    assert context.specification.status == SpecificationStatus.APPROVED
    assert context.specification.is_construction_authorized() is True


# 6. Rejection transitions to CANCELLED
def test_orchestrator_rejection(orchestrator):
    project_id = uuid4()
    req_text = "Every Monday at 8:00 AM, send an email report from PostgreSQL customers table."

    context = orchestrator.start_task(project_id, req_text)
    orchestrator.submit_specification_for_review(context)

    # Reject
    orchestrator.record_human_approval(
        context,
        version_number=1,
        approver="lead_architect_sarah",
        decision="REJECTED",
        comments="Not aligned with current sprint priorities",
    )

    assert context.specification.status == SpecificationStatus.REJECTED
    assert context.current_state == AgentState.CANCELLED
    assert context.state_machine.is_terminal() is True


# 7. Audit Trail Logging
def test_orchestrator_audit_trail(orchestrator, recorded_events):
    events, _ = recorded_events
    project_id = uuid4()
    req_text = "Every Monday at 8:00 AM, send an email report from PostgreSQL customers table."

    context = orchestrator.start_task(project_id, req_text)
    orchestrator.submit_specification_for_review(context)
    orchestrator.record_human_approval(
        context,
        version_number=1,
        approver="reviewer",
        decision="APPROVED",
    )

    # Verify transitions logged
    transition_events = [e for e in events if e.event_type == "workflow.state_transition"]
    assert len(transition_events) >= 2
    assert any(e.event_type == "workflow.state_transition" for e in events)
