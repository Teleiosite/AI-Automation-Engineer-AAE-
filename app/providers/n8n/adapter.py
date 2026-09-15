"""n8n Provider Adapter implementing the canonical AutomationProvider interface."""

from datetime import datetime, timezone
import logging
import re
from typing import Any, Dict, List, Optional

from app.domain.capabilities.models import CapabilityRegistry, get_default_n8n_registry
from app.providers.base import (
    AutomationProvider,
    CapabilityLimitationError,
    ProviderError,
    ProviderExecutionError,
    ProviderValidationError,
    UnsupportedOperationError,
)
from app.providers.models import (
    ProviderExecution,
    ProviderExecutionResult,
    ProviderInstanceInfo,
    ProviderNodeInfo,
    ProviderValidationResult,
    ProviderWorkflow,
)
from app.providers.n8n.client import N8nClient

logger = logging.getLogger(__name__)


def _parse_iso_datetime(dt_str: Optional[str]) -> Optional[datetime]:
    if not dt_str:
        return None
    try:
        # Normalize trailing Z to +00:00
        normalized = dt_str.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    except Exception:
        return None


def _map_workflow_dict_to_provider_workflow(data: Dict[str, Any]) -> ProviderWorkflow:
    return ProviderWorkflow(
        id=str(data.get("id", "")),
        name=data.get("name", "Unnamed Workflow"),
        active=bool(data.get("active", False)),
        version_id=str(data.get("versionId")) if data.get("versionId") else None,
        nodes=data.get("nodes", []),
        connections=data.get("connections", {}),
        settings=data.get("settings", {}),
        created_at=_parse_iso_datetime(data.get("createdAt")),
        updated_at=_parse_iso_datetime(data.get("updatedAt")),
        raw_payload=data,
    )


def _map_execution_dict_to_provider_execution(data: Dict[str, Any]) -> ProviderExecution:
    started = _parse_iso_datetime(data.get("startedAt"))
    stopped = _parse_iso_datetime(data.get("stoppedAt"))
    duration: Optional[float] = None
    if started and stopped:
        duration = max(0.0, (stopped - started).total_seconds() * 1000.0)

    return ProviderExecution(
        id=str(data.get("id", "")),
        workflow_id=str(data.get("workflowId", "")),
        status=str(data.get("status", "unknown")).lower(),
        started_at=started,
        stopped_at=stopped,
        duration_ms=duration,
        mode=data.get("mode", "manual"),
        retry_of=str(data.get("retryOf")) if data.get("retryOf") else None,
        retry_success=data.get("retrySuccess"),
        data=data.get("data"),
    )


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

    # Connectivity & Instance

    def check_health(self) -> bool:
        """Check reachability of the n8n instance."""
        return self.client.check_connectivity()

    def get_instance_info(self) -> ProviderInstanceInfo:
        """Retrieve structured runtime status and instance features."""
        info = self.client.get_instance_info()
        is_healthy = info.get("status") in ("ok", "success") or self.check_health()
        return ProviderInstanceInfo(
            provider="n8n",
            version=self.version,
            status="healthy" if is_healthy else "unreachable",
            base_url=self.client.base_url,
            features={
                "direct_execution": False,  # 405 on 2.38.7
                "webhook_execution": True,
                "api_key_auth": True,
            },
        )

    def get_capabilities(self) -> CapabilityRegistry:
        """Return the capability registry for n8n 2.38.7."""
        return self.capabilities

    # Workflow CRUD

    def list_workflows(
        self,
        limit: int = 50,
        cursor: Optional[str] = None,
        active: Optional[bool] = None,
    ) -> List[ProviderWorkflow]:
        """List workflows managed by n8n."""
        resp = self.client.list_workflows(limit=limit, cursor=cursor, active=active)
        raw_items = resp.get("data", []) if isinstance(resp, dict) else []
        return [_map_workflow_dict_to_provider_workflow(item) for item in raw_items]

    def get_workflow(self, workflow_id: str) -> ProviderWorkflow:
        """Fetch workflow by ID."""
        data = self.client.get_workflow(workflow_id)
        return _map_workflow_dict_to_provider_workflow(data)

    def create_workflow(
        self,
        name: str,
        nodes: List[Dict[str, Any]],
        connections: Dict[str, Any],
        settings: Optional[Dict[str, Any]] = None,
    ) -> ProviderWorkflow:
        """Create a new workflow in n8n."""
        payload = {
            "name": name,
            "nodes": nodes,
            "connections": connections,
            "settings": settings or {},
        }
        data = self.client.create_workflow(payload)
        return _map_workflow_dict_to_provider_workflow(data)

    def update_workflow(
        self,
        workflow_id: str,
        name: Optional[str] = None,
        nodes: Optional[List[Dict[str, Any]]] = None,
        connections: Optional[Dict[str, Any]] = None,
        settings: Optional[Dict[str, Any]] = None,
    ) -> ProviderWorkflow:
        """Update an existing workflow in n8n."""
        current = self.get_workflow(workflow_id)
        payload = {
            "name": name if name is not None else current.name,
            "nodes": nodes if nodes is not None else current.nodes,
            "connections": connections if connections is not None else current.connections,
            "settings": settings if settings is not None else current.settings,
        }
        data = self.client.update_workflow(workflow_id, payload)
        return _map_workflow_dict_to_provider_workflow(data)

    def activate_workflow(self, workflow_id: str) -> ProviderWorkflow:
        """Activate workflow triggers in n8n."""
        data = self.client.activate_workflow(workflow_id)
        return _map_workflow_dict_to_provider_workflow(data)

    def deactivate_workflow(self, workflow_id: str) -> ProviderWorkflow:
        """Deactivate workflow triggers in n8n."""
        data = self.client.deactivate_workflow(workflow_id)
        return _map_workflow_dict_to_provider_workflow(data)

    def delete_workflow(self, workflow_id: str) -> bool:
        """Delete a workflow from n8n."""
        return self.client.delete_workflow(workflow_id)

    # Workflow Execution

    def execute_workflow(
        self,
        workflow_id: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> ProviderExecutionResult:
        """
        Execute workflow following strict capability rules:
        1. Native direct execution (/run) is checked first.
        2. On n8n 2.38.7, native direct execution returns 405 Method Not Allowed.
        3. Webhook workaround (N8N-WA-001) is used when a compatible webhook trigger node is present.
        4. If no compatible webhook trigger node exists, fails closed with CapabilityLimitationError.
        """
        if self.capabilities.is_supported("workflow.execute.native"):
            raise UnsupportedOperationError("Native direct execution is not supported on n8n 2.38.7")

        if not self.capabilities.is_workaround("workflow.execute.webhook"):
            raise CapabilityLimitationError("No execution mechanism or workaround available for this provider.")

        workflow = self.get_workflow(workflow_id)
        nodes = workflow.nodes

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

        parameters = webhook_node.get("parameters", {})
        path = parameters.get("path") or parameters.get("webhookId")
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

        start_time = datetime.now(timezone.utc)
        try:
            result = self.client.trigger_webhook(
                webhook_path=path,
                payload=payload,
                method=http_method,
            )
            duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000.0

            output_dict = {
                "webhook_path": path,
                "provider_result": result,
                **(result if isinstance(result, dict) else {}),
            }
            return ProviderExecutionResult(
                workflow_id=workflow_id,
                status="initiated",
                outcome="SUCCESS",
                execution_id=result.get("executionId") or result.get("id") if isinstance(result, dict) else None,
                duration_ms=duration_ms,
                output_data=output_dict,
                mechanism="workaround",
                workaround_id="N8N-WA-001",
            )
        except Exception as e:
            duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000.0
            return ProviderExecutionResult(
                workflow_id=workflow_id,
                status="failed",
                outcome="FAILED",
                duration_ms=duration_ms,
                error_message=str(e),
                mechanism="workaround",
                workaround_id="N8N-WA-001",
            )

    # Execution History

    def list_executions(
        self,
        workflow_id: Optional[str] = None,
        limit: int = 20,
        cursor: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[ProviderExecution]:
        """List execution history records from n8n."""
        resp = self.client.list_executions(workflow_id=workflow_id, limit=limit, cursor=cursor, status=status)
        raw_items = resp.get("data", []) if isinstance(resp, dict) else []
        return [_map_execution_dict_to_provider_execution(item) for item in raw_items]

    def get_execution(self, execution_id: str) -> ProviderExecution:
        """Fetch detailed execution trace."""
        data = self.client.get_execution(execution_id)
        return _map_execution_dict_to_provider_execution(data)

    def retry_execution(self, execution_id: str) -> ProviderExecution:
        """Request re-execution of a failed execution record."""
        data = self.client.retry_execution(execution_id)
        return _map_execution_dict_to_provider_execution(data)

    # Node Catalog & Validation

    def get_node_info(self, node_type: str) -> Optional[ProviderNodeInfo]:
        """Retrieve node capabilities and schema rules."""
        # Built-in catalog mapping for common n8n nodes
        known_nodes = {
            "n8n-nodes-base.webhook": ProviderNodeInfo(
                node_type="n8n-nodes-base.webhook",
                display_name="Webhook",
                description="Starts the workflow when a webhook is called",
                version=1,
                categories=["Development", "Core Nodes"],
                inputs=[],
                outputs=["main"],
                properties=[{"name": "path", "type": "string", "required": True}],
            ),
            "n8n-nodes-base.httpRequest": ProviderNodeInfo(
                node_type="n8n-nodes-base.httpRequest",
                display_name="HTTP Request",
                description="Makes an HTTP request and returns the data",
                version=4,
                categories=["Development"],
                inputs=["main"],
                outputs=["main"],
                properties=[{"name": "url", "type": "string", "required": True}],
            ),
            "n8n-nodes-base.set": ProviderNodeInfo(
                node_type="n8n-nodes-base.set",
                display_name="Edit Fields (Set)",
                description="Set values on items",
                version=3,
                categories=["Core Nodes"],
                inputs=["main"],
                outputs=["main"],
            ),
            "n8n-nodes-base.scheduleTrigger": ProviderNodeInfo(
                node_type="n8n-nodes-base.scheduleTrigger",
                display_name="Schedule Trigger",
                description="Triggers the workflow at specified time intervals",
                version=1,
                categories=["Core Nodes"],
                inputs=[],
                outputs=["main"],
            ),
        }
        return known_nodes.get(node_type)

    def validate_workflow(self, workflow_data: Dict[str, Any]) -> ProviderValidationResult:
        """Validate workflow structure, nodes, connections, and required fields."""
        errors: List[str] = []
        warnings: List[str] = []
        unsupported: List[str] = []

        nodes = workflow_data.get("nodes")
        if not isinstance(nodes, list) or len(nodes) == 0:
            errors.append("Workflow must contain at least one node in 'nodes' array")
            return ProviderValidationResult(is_valid=False, errors=errors)

        node_names = set()
        for idx, node in enumerate(nodes):
            if not isinstance(node, dict):
                errors.append(f"Node at index {idx} must be a JSON object")
                continue
            name = node.get("name")
            node_type = node.get("type")
            if not name:
                errors.append(f"Node at index {idx} is missing required 'name' attribute")
            elif name in node_names:
                errors.append(f"Duplicate node name detected: '{name}'")
            else:
                node_names.add(name)

            if not node_type:
                errors.append(f"Node '{name or idx}' is missing required 'type' attribute")

        # Validate connections
        connections = workflow_data.get("connections", {})
        if isinstance(connections, dict):
            for source_name, conn_data in connections.items():
                if source_name not in node_names:
                    errors.append(f"Connection references non-existent source node '{source_name}'")
                if isinstance(conn_data, dict):
                    for output_type, targets in conn_data.items():
                        if isinstance(targets, list):
                            for target_group in targets:
                                if isinstance(target_group, list):
                                    for target in target_group:
                                        target_node = target.get("node")
                                        if target_node and target_node not in node_names:
                                            errors.append(f"Connection from '{source_name}' references non-existent target '{target_node}'")

        is_valid = len(errors) == 0
        return ProviderValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            unsupported_nodes=unsupported,
        )

    def security_audit(self, workflow_data: Dict[str, Any]) -> Dict[str, Any]:
        """Scan workflow definition for sensitive parameter leakage or dangerous nodes."""
        findings: List[Dict[str, Any]] = []
        risk_level = "LOW"

        nodes = workflow_data.get("nodes", [])
        secret_pattern = re.compile(r"(password|secret|token|api_key|credential|private_key)", re.IGNORECASE)

        for node in nodes:
            node_name = node.get("name", "Unknown")
            node_type = node.get("type", "")

            # Check 1: High risk command execution nodes
            if "executecommand" in node_type.lower() or "ssh" in node_type.lower():
                findings.append({
                    "severity": "CRITICAL",
                    "node": node_name,
                    "issue": f"Arbitrary command execution node detected: '{node_type}'",
                    "recommendation": "Require explicit security approval before execution.",
                })
                risk_level = "CRITICAL"

            # Check 2: Unauthenticated Webhooks
            if "webhook" in node_type.lower():
                params = node.get("parameters", {})
                auth = params.get("authentication", "none")
                if auth in ("none", "", None):
                    findings.append({
                        "severity": "MEDIUM",
                        "node": node_name,
                        "issue": "Webhook trigger configured with no authentication",
                        "recommendation": "Configure headerAuth or basicAuth on production webhooks.",
                    })
                    if risk_level != "CRITICAL":
                        risk_level = "MEDIUM"

            # Check 3: Hardcoded secrets in parameters
            parameters = node.get("parameters", {})
            for k, v in parameters.items():
                if secret_pattern.search(k) and isinstance(v, str) and not v.startswith("={{"):
                    findings.append({
                        "severity": "HIGH",
                        "node": node_name,
                        "parameter": k,
                        "issue": f"Plaintext credential detected in parameter '{k}'",
                        "recommendation": "Use n8n credential store or environment expression instead of plaintext.",
                    })
                    if risk_level != "CRITICAL":
                        risk_level = "HIGH"

        return {
            "status": "FLAGGED" if findings else "PASSED",
            "risk_level": risk_level,
            "findings_count": len(findings),
            "findings": findings,
        }
