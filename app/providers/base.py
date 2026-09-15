"""Abstract Base Class for Automation Providers."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from app.domain.capabilities.models import CapabilityRegistry
from app.providers.errors import (
    CapabilityLimitationError,
    ProviderAuthenticationError,
    ProviderAuthorizationError,
    ProviderConflictError,
    ProviderConnectionError,
    ProviderError,
    ProviderExecutionError,
    ProviderNotFoundError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    ProviderValidationError,
    ProviderVersionError,
    UnknownProviderError,
    UnsupportedOperationError,
)
from app.providers.models import (
    ProviderExecution,
    ProviderExecutionResult,
    ProviderInstanceInfo,
    ProviderNodeInfo,
    ProviderValidationResult,
    ProviderWorkflow,
    ProviderWorkflowVersion,
)


class AutomationProvider(ABC):
    """
    Canonical provider-neutral integration boundary.
    All external orchestration platforms (e.g. n8n) must be adapted through this contract.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier (e.g. 'n8n')."""
        pass

    @property
    @abstractmethod
    def version(self) -> str:
        """Provider server engine version."""
        pass

    @abstractmethod
    def check_health(self) -> bool:
        """Verify network reachability and basic readiness."""
        pass

    @abstractmethod
    def get_instance_info(self) -> ProviderInstanceInfo:
        """Retrieve structured runtime status and instance features."""
        pass

    @abstractmethod
    def get_capabilities(self) -> CapabilityRegistry:
        """Return the capability registry for this provider."""
        pass

    @abstractmethod
    def list_workflows(
        self,
        limit: int = 50,
        cursor: Optional[str] = None,
        active: Optional[bool] = None,
    ) -> List[ProviderWorkflow]:
        """List workflows managed by the provider."""
        pass

    @abstractmethod
    def get_workflow(self, workflow_id: str) -> ProviderWorkflow:
        """Fetch workflow definition by ID."""
        pass

    @abstractmethod
    def create_workflow(
        self,
        name: str,
        nodes: List[Dict[str, Any]],
        connections: Dict[str, Any],
        settings: Optional[Dict[str, Any]] = None,
    ) -> ProviderWorkflow:
        """Create a new workflow in the provider."""
        pass

    @abstractmethod
    def update_workflow(
        self,
        workflow_id: str,
        name: Optional[str] = None,
        nodes: Optional[List[Dict[str, Any]]] = None,
        connections: Optional[Dict[str, Any]] = None,
        settings: Optional[Dict[str, Any]] = None,
    ) -> ProviderWorkflow:
        """Update an existing workflow in the provider."""
        pass

    @abstractmethod
    def activate_workflow(self, workflow_id: str) -> ProviderWorkflow:
        """Enable/activate workflow triggers in the provider."""
        pass

    @abstractmethod
    def deactivate_workflow(self, workflow_id: str) -> ProviderWorkflow:
        """Disable/deactivate workflow triggers in the provider."""
        pass

    @abstractmethod
    def delete_workflow(self, workflow_id: str) -> bool:
        """Delete a workflow from the provider."""
        pass

    @abstractmethod
    def execute_workflow(
        self,
        workflow_id: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> ProviderExecutionResult:
        """Execute a workflow according to verified provider capabilities or authorized workarounds."""
        pass

    @abstractmethod
    def list_executions(
        self,
        workflow_id: Optional[str] = None,
        limit: int = 20,
        cursor: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[ProviderExecution]:
        """List execution history from provider."""
        pass

    @abstractmethod
    def get_execution(self, execution_id: str) -> ProviderExecution:
        """Retrieve detailed execution trace by execution ID."""
        pass

    @abstractmethod
    def retry_execution(self, execution_id: str) -> ProviderExecution:
        """Request re-execution of a failed execution record."""
        pass

    @abstractmethod
    def get_node_info(self, node_type: str) -> Optional[ProviderNodeInfo]:
        """Fetch capability schema and metadata for a provider node type."""
        pass

    @abstractmethod
    def validate_workflow(self, workflow_data: Dict[str, Any]) -> ProviderValidationResult:
        """Validate workflow structure, nodes, connections, and expressions against provider rules."""
        pass

    @abstractmethod
    def security_audit(self, workflow_data: Dict[str, Any]) -> Dict[str, Any]:
        """Scan workflow definition for security vulnerabilities, hardcoded secrets, and unsafe nodes."""
        pass
