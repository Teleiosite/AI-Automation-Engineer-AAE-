"""n8n Provider Adapter implementing AutomationProvider."""

import logging
from typing import Any, Dict, Optional
from app.domain.capabilities.models import CapabilityRegistry, get_default_n8n_registry
from app.providers.base import AutomationProvider, CapabilityLimitationError, ProviderError
from app.providers.n8n.client import N8nClient

logger = logging.getLogger(__name__)


class N8nProvider(AutomationProvider):
    """Concrete automation provider adapter for n8n 2.38.7."""

    def __init__(
        self,
        client: Optional[N8nClient] = None,
        capabilities: Optional[CapabilityRegistry] = None,
    ) -> None:
        self.client = client or N8nClient()
        self.capabilities = capabilities or get_default_n8n_registry()

    @property
    def name(self) -> str:
        return "n8n"

    @property
    def version(self) -> str:
        return "2.38.7"

    def check_health(self) -> bool:
        """Check reachability of the n8n instance."""
        return self.client.check_connectivity()

    def get_capabilities(self) -> CapabilityRegistry:
        """Return the capability registry for n8n 2.38.7."""
        return self.capabilities

    def get_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """Fetch workflow JSON definition."""
        return self.client.get_workflow(workflow_id)

    def execute_workflow(
        self,
        workflow_id: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute workflow following strict capability rules:
        1. Native execution capability is checked first.
        2. If native is unsupported, checks workaround applicability.
        3. Compatible webhook available?
           YES -> use verified workaround (N8N-WA-001).
           NO  -> return explicit capability limitation.
        """
        # Step 1: Check native execution
        if self.capabilities.is_supported("workflow.execute.native"):
            raise NotImplementedError("Native direct execution is not supported on n8n 2.38.7")

        # Step 2: Check workaround applicability
        if not self.capabilities.is_workaround("workflow.execute.webhook"):
            raise CapabilityLimitationError("No execution mechanism or workaround available for this provider.")

        # Step 3: Inspect workflow to check for compatible webhook trigger node
        workflow = self.get_workflow(workflow_id)
        nodes = workflow.get("nodes", [])

        webhook_node = None
        for node in nodes:
            node_type = node.get("type", "")
            if "webhook" in node_type.lower():
                webhook_node = node
                break

        if not webhook_node:
            logger.warning(
                "Execution rejected: Workflow %s lacks compatible webhook trigger node",
                workflow_id,
            )
            raise CapabilityLimitationError(
                f"Workflow '{workflow_id}' lacks a compatible webhook trigger node for workaround N8N-WA-001; "
                "native execution is unsupported on n8n 2.38.7."
            )

        # Extract webhook parameters
        parameters = webhook_node.get("parameters", {})
        path = parameters.get("path")
        if not path:
            # Check webhookId fallback
            path = parameters.get("webhookId")

        if not path:
            raise CapabilityLimitationError(
                f"Webhook node in workflow '{workflow_id}' has no configured webhook path."
            )

        http_method = parameters.get("httpMethod", "POST")

        logger.info(
            "Executing workflow %s via verified workaround N8N-WA-001 on path %s",
            workflow_id,
            path,
        )

        result = self.client.trigger_webhook(
            webhook_path=path,
            payload=payload,
            method=http_method,
        )

        return {
            "execution_status": "initiated",
            "mechanism": "workaround",
            "workaround_id": "N8N-WA-001",
            "workflow_id": workflow_id,
            "webhook_path": path,
            "provider_result": result,
        }
