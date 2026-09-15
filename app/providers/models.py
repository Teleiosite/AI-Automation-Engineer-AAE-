"""Provider-neutral data representations and contracts."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class ProviderInstanceInfo:
    """Status and metadata for an automation provider instance."""
    provider: str
    version: str
    status: str  # "healthy", "unreachable", "degraded"
    base_url: str
    features: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderWorkflow:
    """Provider-neutral representation of a workflow definition."""
    id: str
    name: str
    active: bool
    version_id: Optional[str] = None
    nodes: List[Dict[str, Any]] = field(default_factory=list)
    connections: Dict[str, Any] = field(default_factory=dict)
    settings: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    raw_payload: Optional[Dict[str, Any]] = None

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)


@dataclass(frozen=True)
class ProviderWorkflowVersion:
    """Versioned immutable snapshot of a workflow definition in provider."""
    version_id: str
    workflow_id: str
    definition: Dict[str, Any]
    created_at: Optional[datetime] = None


@dataclass(frozen=True)
class ProviderExecution:
    """Runtime execution record in the provider."""
    id: str
    workflow_id: str
    status: str  # "success", "error", "running", "waiting", "canceled"
    started_at: Optional[datetime] = None
    stopped_at: Optional[datetime] = None
    duration_ms: Optional[float] = None
    mode: str = "manual"
    retry_of: Optional[str] = None
    retry_success: Optional[bool] = None
    data: Optional[Dict[str, Any]] = None

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)


@dataclass(frozen=True)
class ProviderExecutionResult:
    """Outcome of initiating or completing a workflow execution."""
    workflow_id: str
    status: str  # "initiated", "success", "failed", "rejected"
    outcome: str  # "SUCCESS", "FAILED", "UNKNOWN"
    execution_id: Optional[str] = None
    duration_ms: Optional[float] = None
    output_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None
    mechanism: str = "native"  # "native" or "workaround"
    workaround_id: Optional[str] = None

    def __getitem__(self, key: str) -> Any:
        """Allow subscript access for backward compatibility with dictionary tests."""
        compat_map = {
            "execution_status": self.status,
            "mechanism": self.mechanism,
            "workaround_id": self.workaround_id,
            "workflow_id": self.workflow_id,
            "webhook_path": (self.output_data or {}).get("webhook_path") if isinstance(self.output_data, dict) else None,
            "provider_result": (self.output_data or {}).get("provider_result") if isinstance(self.output_data, dict) else self.output_data,
        }
        if key in compat_map:
            return compat_map[key]
        if hasattr(self, key):
            return getattr(self, key)
        if isinstance(self.output_data, dict) and key in self.output_data:
            return self.output_data[key]
        raise KeyError(key)


@dataclass(frozen=True)
class ProviderNodeInfo:
    """Metadata describing a specific provider node type."""
    node_type: str
    display_name: str
    description: str
    version: int
    categories: List[str] = field(default_factory=list)
    inputs: List[str] = field(default_factory=list)
    outputs: List[str] = field(default_factory=list)
    properties: List[Dict[str, Any]] = field(default_factory=list)
    credentials: List[Dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class ProviderValidationResult:
    """Result of validating a workflow against provider schema rules."""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    unsupported_nodes: List[str] = field(default_factory=list)
    unverified_expressions: List[str] = field(default_factory=list)
