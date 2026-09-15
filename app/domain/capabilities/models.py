"""Capability Registry models enforcing capability truthfulness using Python standard library."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional


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


class CapabilityRegistry:
    """Registry maintaining verified provider capabilities."""

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

    def list_all(self) -> List[Capability]:
        """Return all registered capabilities."""
        return list(self._capabilities.values())


def get_default_n8n_registry() -> CapabilityRegistry:
    """Instantiate and populate the baseline n8n 2.38.7 capability registry."""
    registry = CapabilityRegistry()

    # Runtime Verified Capabilities
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
        name="execution.get",
        status=CapabilityStatus.RUNTIME_VERIFIED,
        evidence=[CapabilityEvidence(evidence_type="runtime_test", details="GET /api/v1/executions/{id} returned execution data")]
    ))

    # Workaround Available: Webhook execution
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

    # Unsupported: Native Direct Execution
    registry.register(Capability(
        name="workflow.execute.native",
        status=CapabilityStatus.UNSUPPORTED,
        risk="high",
        evidence=[CapabilityEvidence(
            evidence_type="error_response",
            details="POST /api/v1/workflows/{id}/run returned 405 Method Not Allowed"
        )]
    ))

    # Known Limitations
    registry.register(Capability(
        name="openapi.specification",
        status=CapabilityStatus.KNOWN_LIMITATION,
        evidence=[CapabilityEvidence(
            evidence_type="runtime_test",
            details="GET /openapi.json returned n8n Web Editor HTML instead of OpenAPI JSON"
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

    # Unknown Capabilities
    registry.register(Capability(
        name="workflow.validate.native",
        status=CapabilityStatus.UNKNOWN,
        evidence=[CapabilityEvidence(
            evidence_type="documentation_gap",
            details="No verified native /validate endpoint on n8n 2.38.7"
        )]
    ))

    return registry
