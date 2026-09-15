"""Abstract Base Class for Automation Providers."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from app.domain.capabilities.models import CapabilityRegistry


class ProviderError(Exception):
    """Base exception for provider operations."""
    pass


class CapabilityLimitationError(ProviderError):
    """Raised when an operation cannot be performed due to provider limitations."""
    pass


class AutomationProvider(ABC):
    """Provider-neutral interface for automation platforms."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier."""
        pass

    @property
    @abstractmethod
    def version(self) -> str:
        """Provider version."""
        pass

    @abstractmethod
    def check_health(self) -> bool:
        """Verify provider connectivity."""
        pass

    @abstractmethod
    def get_capabilities(self) -> CapabilityRegistry:
        """Return the capability registry for this provider."""
        pass

    @abstractmethod
    def get_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """Fetch workflow by ID."""
        pass

    @abstractmethod
    def execute_workflow(self, workflow_id: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute a workflow according to provider capabilities or verified workarounds."""
        pass
