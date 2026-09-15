"""Capability Registry models enforcing capability truthfulness using Python standard library."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class CapabilityStatus(str, Enum):
    """Permitted capability classifications."""
    RUNTIME_VERIFIED = "RUNTIME_VERIFIED"
    DOCUMENTED = "DOCUMENTED"
    VERSION_DEPENDENT = "VERSION_DEPENDENT"
    PLAN_DEPENDENT = "PLAN_DEPENDENT"
    PERMISSION_DEPENDENT = "PERMISSION_DEPENDENT"
    ENVIRONMENT_DEPENDENT = "ENVIRONMENT_DEPENDENT"
    WORKAROUND_AVAILABLE = "WORKAROUND_AVAILABLE"
    KNOWN_LIMITATION = "KNOWN_LIMITATION"
    UNKNOWN = "UNKNOWN"
    UNSUPPORTED = "UNSUPPORTED"


@dataclass
class CapabilityEvidence:
    """Evidence supporting a capability status."""
    evidence_type: str
    details: str
    verified_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Capability:
    """Representation of an automation provider capability."""
    name: str
    status: CapabilityStatus
    provider: str = "n8n"
    provider_version: str = "2.38.7"
    risk: str = "low"
    workaround_id: Optional[str] = None
    evidence: List[CapabilityEvidence] = field(default_factory=list)
    last_verified: Optional[datetime] = None


@dataclass(frozen=True)
class CapabilityDecision:
    """Outcome of a capability evaluation."""
    allowed: bool
    capability_name: str
    status: CapabilityStatus
    reason: str
    workaround_id: Optional[str] = None
    required_action: Optional[str] = None


class CapabilityRegistry:
    """Registry maintaining verified provider capabilities and evaluating operation feasibility."""

    def __init__(self) -> None:
        self._capabilities: Dict[str, Capability] = {}

    def register(self, capability: Capability) -> None:
        """Register or update a capability."""
        self._capabilities[capability.name] = capability

    def get(self, name: str) -> Optional[Capability]:
        """Retrieve capability by name."""
        return self._capabilities.get(name)

    def is_supported(self, name: str) -> bool:
        """Check if capability is directly supported without workarounds."""
        cap = self.get(name)
        if not cap:
            return False
        return cap.status in (CapabilityStatus.RUNTIME_VERIFIED, CapabilityStatus.DOCUMENTED)

    def is_workaround(self, name: str) -> bool:
        """Check if capability requires an indirect workaround."""
        cap = self.get(name)
        if not cap:
            return False
        return cap.status == CapabilityStatus.WORKAROUND_AVAILABLE

    def is_unsupported(self, name: str) -> bool:
        """Check if capability is explicitly unsupported."""
        cap = self.get(name)
        if not cap:
            return False
        return cap.status == CapabilityStatus.UNSUPPORTED

    def is_unknown(self, name: str) -> bool:
        """Check if capability has unknown status."""
        cap = self.get(name)
        if not cap:
            return True  # Unregistered capabilities are treated as UNKNOWN
        return cap.status == CapabilityStatus.UNKNOWN

    def is_known_limitation(self, name: str) -> bool:
        """Check if capability is an accepted known limitation."""
        cap = self.get(name)
        if not cap:
            return False
        return cap.status == CapabilityStatus.KNOWN_LIMITATION

    def list_all(self) -> List[Capability]:
        """Return all registered capabilities."""
        return list(self._capabilities.values())

    def list_by_status(self, status: CapabilityStatus) -> List[Capability]:
        """Return capabilities matching a specific classification."""
        return [c for c in self._capabilities.values() if c.status == status]

    def evaluate(self, operation_name: str) -> CapabilityDecision:
        """
        Evaluate whether an operation is permitted to execute.
        Strict capability rules:
        1. UNREGISTERED -> Denied (UNKNOWN).
        2. UNKNOWN -> Denied. Requires empirical verification.
        3. UNSUPPORTED -> Denied. Direct invocation prohibited.
        4. KNOWN_LIMITATION -> Denied. Native invocation prohibited.
        5. WORKAROUND_AVAILABLE -> Denied natively; requires designated workaround.
        6. RUNTIME_VERIFIED / DOCUMENTED -> Allowed.
        """
        cap = self.get(operation_name)
        if not cap:
            return CapabilityDecision(
                allowed=False,
                capability_name=operation_name,
                status=CapabilityStatus.UNKNOWN,
                reason=f"Operation '{operation_name}' is not registered in the capability catalog.",
                required_action="Register capability with supporting empirical evidence before attempting execution.",
            )

        if cap.status == CapabilityStatus.UNSUPPORTED:
            return CapabilityDecision(
                allowed=False,
                capability_name=operation_name,
                status=CapabilityStatus.UNSUPPORTED,
                reason=f"Operation '{operation_name}' is UNSUPPORTED by {cap.provider} {cap.provider_version}.",
                required_action="Do not execute. Redesign workflow to avoid this operation.",
            )

        if cap.status == CapabilityStatus.UNKNOWN:
            return CapabilityDecision(
                allowed=False,
                capability_name=operation_name,
                status=CapabilityStatus.UNKNOWN,
                reason=f"Operation '{operation_name}' status is UNKNOWN on {cap.provider} {cap.provider_version}.",
                required_action="Perform non-destructive verification in development environment before enabling.",
            )

        if cap.status == CapabilityStatus.KNOWN_LIMITATION:
            return CapabilityDecision(
                allowed=False,
                capability_name=operation_name,
                status=CapabilityStatus.KNOWN_LIMITATION,
                reason=f"Operation '{operation_name}' is a KNOWN_LIMITATION of {cap.provider} {cap.provider_version}.",
                required_action="Use internal AAE capability or alternative provider mechanism.",
            )

        if cap.status == CapabilityStatus.WORKAROUND_AVAILABLE:
            return CapabilityDecision(
                allowed=False,
                capability_name=operation_name,
                status=CapabilityStatus.WORKAROUND_AVAILABLE,
                reason=f"Operation '{operation_name}' is not natively executable; verified workaround '{cap.workaround_id}' is required.",
                workaround_id=cap.workaround_id,
                required_action=f"Invoke via registered workaround {cap.workaround_id}.",
            )

        # RUNTIME_VERIFIED or DOCUMENTED
        return CapabilityDecision(
            allowed=True,
            capability_name=operation_name,
            status=cap.status,
            reason=f"Operation '{operation_name}' is verified ({cap.status.value}) on {cap.provider} {cap.provider_version}.",
        )


def get_default_n8n_registry() -> CapabilityRegistry:
    """Instantiate and populate the baseline n8n 2.38.7 capability registry."""
    registry = CapabilityRegistry()

    # 1. Instance & Connectivity
    registry.register(Capability(
        name="instance.connectivity",
        status=CapabilityStatus.RUNTIME_VERIFIED,
        evidence=[CapabilityEvidence(evidence_type="runtime_test", details="HTTP GET / returned 200 OK")]
    ))
    registry.register(Capability(
        name="auth.api_key",
        status=CapabilityStatus.RUNTIME_VERIFIED,
        evidence=[CapabilityEvidence(evidence_type="runtime_test", details="X-N8N-API-KEY header authenticated")]
    ))

    # 2. Workflows
    registry.register(Capability(
        name="workflow.list",
        status=CapabilityStatus.RUNTIME_VERIFIED,
        evidence=[CapabilityEvidence(evidence_type="runtime_test", details="GET /api/v1/workflows returned workflow array")]
    ))
    registry.register(Capability(
        name="workflow.get",
        status=CapabilityStatus.RUNTIME_VERIFIED,
        evidence=[CapabilityEvidence(evidence_type="runtime_test", details="GET /api/v1/workflows/{id} returned workflow object")]
    ))
    registry.register(Capability(
        name="workflow.create",
        status=CapabilityStatus.RUNTIME_VERIFIED,
        evidence=[CapabilityEvidence(evidence_type="runtime_test", details="POST /api/v1/workflows created workflow")]
    ))
    registry.register(Capability(
        name="workflow.update",
        status=CapabilityStatus.RUNTIME_VERIFIED,
        evidence=[CapabilityEvidence(evidence_type="runtime_test", details="PUT /api/v1/workflows/{id} updated workflow")]
    ))
    registry.register(Capability(
        name="workflow.activate",
        status=CapabilityStatus.RUNTIME_VERIFIED,
        evidence=[CapabilityEvidence(evidence_type="runtime_test", details="POST /api/v1/workflows/{id}/activate succeeded")]
    ))
    registry.register(Capability(
        name="workflow.deactivate",
        status=CapabilityStatus.RUNTIME_VERIFIED,
        evidence=[CapabilityEvidence(evidence_type="runtime_test", details="POST /api/v1/workflows/{id}/deactivate succeeded")]
    ))
    registry.register(Capability(
        name="workflow.delete",
        status=CapabilityStatus.UNKNOWN,
        evidence=[CapabilityEvidence(evidence_type="documentation_gap", details="DELETE /api/v1/workflows/{id} documented but requires explicit verification")]
    ))

    # 3. Executions
    registry.register(Capability(
        name="execution.list",
        status=CapabilityStatus.RUNTIME_VERIFIED,
        evidence=[CapabilityEvidence(evidence_type="runtime_test", details="GET /api/v1/executions returned history records")]
    ))
    registry.register(Capability(
        name="execution.get",
        status=CapabilityStatus.RUNTIME_VERIFIED,
        evidence=[CapabilityEvidence(evidence_type="runtime_test", details="GET /api/v1/executions/{id} returned execution trace")]
    ))
    registry.register(Capability(
        name="execution.get.data",
        status=CapabilityStatus.RUNTIME_VERIFIED,
        evidence=[CapabilityEvidence(evidence_type="runtime_test", details="Execution output payload inspected in test data")]
    ))
    registry.register(Capability(
        name="execution.retry",
        status=CapabilityStatus.UNKNOWN,
        evidence=[CapabilityEvidence(evidence_type="documentation_gap", details="POST /api/v1/executions/{id}/retry unverified in current n8n version")]
    ))

    # 4. Workflow Execution
    registry.register(Capability(
        name="workflow.execute.native",
        status=CapabilityStatus.UNSUPPORTED,
        risk="high",
        evidence=[CapabilityEvidence(
            evidence_type="error_response",
            details="POST /api/v1/workflows/{id}/run returned 405 Method Not Allowed"
        )]
    ))
    registry.register(Capability(
        name="workflow.execute.webhook",
        status=CapabilityStatus.WORKAROUND_AVAILABLE,
        workaround_id="N8N-WA-001",
        risk="moderate",
        evidence=[CapabilityEvidence(
            evidence_type="runtime_test",
            details="POST /webhook/aae-webhook-test initiated execution record"
        )]
    ))

    # 5. Validation & Specification
    registry.register(Capability(
        name="openapi.specification",
        status=CapabilityStatus.KNOWN_LIMITATION,
        evidence=[CapabilityEvidence(
            evidence_type="runtime_test",
            details="GET /openapi.json returned n8n Web Editor HTML instead of OpenAPI JSON"
        )]
    ))
    registry.register(Capability(
        name="workflow.validate.native",
        status=CapabilityStatus.UNKNOWN,
        evidence=[CapabilityEvidence(
            evidence_type="documentation_gap",
            details="No verified native /validate endpoint on n8n 2.38.7; AAE must own deterministic validation"
        )]
    ))
    registry.register(Capability(
        name="runner.python.internal",
        status=CapabilityStatus.KNOWN_LIMITATION,
        evidence=[CapabilityEvidence(
            evidence_type="runtime_test",
            details="n8n internal Python task runner is non-functional in current Windows environment"
        )]
    ))

    # 6. Diagnostics, Repair, & Security
    registry.register(Capability(
        name="failure.inspect",
        status=CapabilityStatus.RUNTIME_VERIFIED,
        evidence=[CapabilityEvidence(evidence_type="runtime_test", details="Failure traces extracted from execution JSON")]
    ))
    registry.register(Capability(
        name="workflow.version.inspect",
        status=CapabilityStatus.RUNTIME_VERIFIED,
        evidence=[CapabilityEvidence(evidence_type="runtime_test", details="Version identifiers present in workflow payloads")]
    ))
    registry.register(Capability(
        name="failure.diagnose",
        status=CapabilityStatus.RUNTIME_VERIFIED,
        evidence=[CapabilityEvidence(evidence_type="domain_logic", details="AAE domain diagnostician parses error categories")]
    ))
    registry.register(Capability(
        name="workflow.repair",
        status=CapabilityStatus.RUNTIME_VERIFIED,
        evidence=[CapabilityEvidence(evidence_type="domain_logic", details="AAE repair engine synthesizes patches")]
    ))
    registry.register(Capability(
        name="workflow.retest",
        status=CapabilityStatus.RUNTIME_VERIFIED,
        evidence=[CapabilityEvidence(evidence_type="domain_logic", details="Repaired workflows executed through testing runner")]
    ))
    registry.register(Capability(
        name="security.audit",
        status=CapabilityStatus.DOCUMENTED,
        evidence=[CapabilityEvidence(evidence_type="specification", details="Security policy §19 static scan implemented")]
    ))

    return registry
