"""Comprehensive Audit & Governance Domain Service (Security Policy §40-45)."""

import hashlib
import json
from typing import Any, Callable, Dict, List, Optional
from uuid import UUID

from app.domain.models.approval import Approval
from app.domain.models.audit import AuditEvent
from app.domain.policy.models import PolicyDecision


def compute_state_hash(state: Any) -> str:
    """Generate deterministic SHA-256 hash of a dictionary or string state."""
    if state is None:
        return "none"
    if isinstance(state, dict) or isinstance(state, list):
        serialized = json.dumps(state, sort_keys=True, default=str)
    else:
        serialized = str(state)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


class AuditService:
    """
    Domain service for orchestrating immutable audit records across:
    - Security decisions
    - Governance approval lifecycle
    - Workflow mutations with before/after state hashes
    - Deployment authorizations and activations
    - Provider operations
    """

    def __init__(self, sink: Optional[Callable[[AuditEvent], Any]] = None) -> None:
        self._sink = sink
        self._events: List[AuditEvent] = []

    def _publish(self, event: AuditEvent) -> AuditEvent:
        self._events.append(event)
        if self._sink:
            self._sink(event)
        return event

    def get_buffered_events(self) -> List[AuditEvent]:
        """Return all audit events buffered in this service instance."""
        return list(self._events)

    def list_by_target(self, target_type: str, target_id: str) -> List[AuditEvent]:
        """Query buffered audit log by target entity."""
        return [
            e for e in self._events
            if e.target_type == target_type and e.target_id == target_id
        ]

    def record_security_decision(
        self,
        actor: str,
        decision: PolicyDecision,
        target_type: str,
        target_id: str,
        correlation_id: Optional[str] = None,
    ) -> AuditEvent:
        """Record an evaluated security policy decision."""
        event = AuditEvent(
            event_type="security.decision",
            actor=actor,
            target_type=target_type,
            target_id=target_id,
            correlation_id=correlation_id,
            outcome=decision.decision.value,
            metadata={
                "action": decision.action.value,
                "risk_level": decision.risk_level.value,
                "reason": decision.reason,
                "required_role": decision.required_role.value if decision.required_role else None,
                "required_approval": decision.required_approval_type,
            },
        )
        return self._publish(event)

    def record_approval_lifecycle(
        self,
        event_name: str,
        approval: Approval,
        actor: str,
        correlation_id: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> AuditEvent:
        """
        Record an approval event (created, decided, consumed, expired).
        """
        event = AuditEvent(
            event_type=f"approval.{event_name}",
            actor=actor,
            target_type="approval",
            target_id=str(approval.id),
            correlation_id=correlation_id,
            outcome=approval.status.value,
            metadata={
                "target_type": approval.target_type,
                "target_id": str(approval.target_id),
                "target_version": approval.target_version,
                "action": approval.action,
                "environment": approval.environment,
                "notes": notes,
                "consumed_by_action_id": str(approval.consumed_by_action_id) if approval.consumed_by_action_id else None,
            },
        )
        return self._publish(event)

    def record_workflow_mutation(
        self,
        mutation_type: str,
        workflow_id: str,
        actor: str,
        version_number: int,
        before_state: Optional[Any] = None,
        after_state: Optional[Any] = None,
        change_reason: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> AuditEvent:
        """
        Record a material workflow definition or state change with before/after state hashes.
        """
        before_hash = compute_state_hash(before_state) if before_state is not None else None
        after_hash = compute_state_hash(after_state) if after_state is not None else None

        event = AuditEvent(
            event_type=f"workflow.{mutation_type}",
            actor=actor,
            target_type="workflow",
            target_id=workflow_id,
            correlation_id=correlation_id,
            outcome="SUCCESS",
            metadata={
                "version_number": version_number,
                "before_hash": before_hash,
                "after_hash": after_hash,
                "change_reason": change_reason or "Material mutation",
            },
        )
        return self._publish(event)

    def record_deployment_event(
        self,
        deployment_id: str,
        workflow_id: str,
        version_number: int,
        environment: str,
        actor: str,
        approval_id: Optional[UUID] = None,
        status: str = "SUCCESS",
        correlation_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> AuditEvent:
        """Record an authorized workflow deployment run."""
        event = AuditEvent(
            event_type="deployment.executed",
            actor=actor,
            target_type="deployment",
            target_id=deployment_id,
            correlation_id=correlation_id,
            outcome=status,
            metadata={
                "workflow_id": workflow_id,
                "version_number": version_number,
                "environment": environment,
                "approval_id": str(approval_id) if approval_id else None,
                **(details or {}),
            },
        )
        return self._publish(event)

    def record_provider_operation(
        self,
        provider_name: str,
        operation_name: str,
        target_id: str,
        actor: str,
        outcome: str,
        duration_ms: Optional[float] = None,
        correlation_id: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> AuditEvent:
        """Record low-level external orchestration provider interaction."""
        event = AuditEvent(
            event_type="provider.operation",
            actor=actor,
            target_type=f"{provider_name}.operation",
            target_id=target_id,
            correlation_id=correlation_id,
            outcome=outcome,
            metadata={
                "provider": provider_name,
                "operation": operation_name,
                "duration_ms": duration_ms,
                "error_message": error_message,
            },
        )
        return self._publish(event)
