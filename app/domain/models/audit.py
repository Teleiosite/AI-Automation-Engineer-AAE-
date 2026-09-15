"""Audit event domain model with automated metadata secret scrubbing."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID, uuid4
from app.domain.errors import DomainValidationError


def sanitize_audit_metadata(data: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively cleanse metadata of potential secrets before storing in audit events."""
    sensitive_keys = {"password", "secret", "token", "api_key", "apikey", "auth", "credential", "private_key"}
    cleaned = {}
    for k, v in data.items():
        k_lower = str(k).lower()
        if isinstance(v, dict):
            cleaned[k] = sanitize_audit_metadata(v)
        elif isinstance(v, list):
            cleaned[k] = [
                sanitize_audit_metadata(item)
                if isinstance(item, dict)
                else ("********" if any(s in k_lower for s in sensitive_keys) else item)
                for item in v
            ]
        elif any(s in k_lower for s in sensitive_keys):
            cleaned[k] = "********"
        else:
            cleaned[k] = v
    return cleaned


@dataclass(frozen=True)
class AuditEvent:
    """Security-conscious immutable audit event."""
    event_type: str
    actor: str
    target_type: str
    target_id: str
    id: UUID = field(default_factory=uuid4)
    correlation_id: Optional[str] = None
    outcome: str = "SUCCESS"
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if not self.event_type or not self.event_type.strip():
            raise DomainValidationError("Audit event type cannot be empty")
        if not self.actor or not self.actor.strip():
            raise DomainValidationError("Audit actor cannot be empty")
        if self.timestamp.tzinfo is None:
            raise DomainValidationError("Timestamps must be timezone-aware UTC")

        # Object is frozen, so set sanitized metadata via object.__setattr__
        sanitized = sanitize_audit_metadata(self.metadata)
        object.__setattr__(self, "metadata", sanitized)