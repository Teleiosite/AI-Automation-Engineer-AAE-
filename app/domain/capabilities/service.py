"""Capability Enforcement Service enforcing deterministic provider gating in the domain layer."""

from typing import Any, Dict, List, Optional

from app.domain.capabilities.models import (
    Capability,
    CapabilityDecision,
    CapabilityEvidence,
    CapabilityRegistry,
    CapabilityStatus,
    get_default_n8n_registry,
)
from app.domain.errors import DomainError


class CapabilityEnforcementError(DomainError):
    """Raised when an operation is rejected due to capability restrictions."""
    pass


class CapabilityEnforcementService:
    """
    Deterministic domain service evaluating provider operations against verified capability evidence.
    Guarantees that no UNKNOWN, UNSUPPORTED, or UNVERIFIED provider action can be initiated.
    """

    def __init__(self, registry: Optional[CapabilityRegistry] = None) -> None:
        self._registry = registry or get_default_n8n_registry()

    @property
    def registry(self) -> CapabilityRegistry:
        return self._registry

    def evaluate(self, operation_name: str) -> CapabilityDecision:
        """Evaluate an operation against registered provider capabilities."""
        return self._registry.evaluate(operation_name)

    def enforce(
        self,
        operation_name: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> CapabilityDecision:
        """
        Enforce capability gating on an operation.
        Raises CapabilityEnforcementError if the operation is not permitted.
        """
        decision = self.evaluate(operation_name)
        if not decision.allowed:
            detail = f"Capability check failed for '{operation_name}': {decision.reason}"
            if decision.required_action:
                detail += f" Action required: {decision.required_action}"
            raise CapabilityEnforcementError(detail)
        return decision

    def record_evidence(
        self,
        operation_name: str,
        evidence_type: str,
        details: str,
    ) -> CapabilityEvidence:
        """Attach empirical evidence to a capability in the registry."""
        cap = self._registry.get(operation_name)
        if not cap:
            raise CapabilityEnforcementError(
                f"Cannot attach evidence to unregistered capability '{operation_name}'"
            )
        evidence = CapabilityEvidence(evidence_type=evidence_type, details=details)
        cap.evidence.append(evidence)
        return evidence

    def update_status(
        self,
        operation_name: str,
        new_status: CapabilityStatus,
        evidence: CapabilityEvidence,
    ) -> Capability:
        """Promote or demote capability status backed by concrete evidence."""
        cap = self._registry.get(operation_name)
        if not cap:
            cap = Capability(name=operation_name, status=new_status, evidence=[evidence])
            self._registry.register(cap)
            return cap

        cap.status = new_status
        cap.evidence.append(evidence)
        return cap

    def list_supported_operations(self) -> List[str]:
        """List all operations currently verified as directly supported."""
        return [
            c.name
            for c in self._registry.list_all()
            if c.status in (CapabilityStatus.RUNTIME_VERIFIED, CapabilityStatus.DOCUMENTED)
        ]

    def list_unsupported_operations(self) -> List[str]:
        """List operations known to be unsupported."""
        return [
            c.name
            for c in self._registry.list_all()
            if c.status == CapabilityStatus.UNSUPPORTED
        ]

    def list_workarounds(self) -> List[Dict[str, Any]]:
        """List operations requiring an indirect workaround."""
        return [
            {
                "operation": c.name,
                "workaround_id": c.workaround_id,
                "risk": c.risk,
            }
            for c in self._registry.list_all()
            if c.status == CapabilityStatus.WORKAROUND_AVAILABLE
        ]
