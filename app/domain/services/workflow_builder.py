"""Workflow Builder Service (Phase 11).

Converts capability-verified WorkflowPlan instances into canonical, structurally compliant,
and secret-scrubbed n8n workflow definitions.
"""

from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID, uuid4

from app.domain.errors import DomainValidationError, InvariantViolationError
from app.domain.models.workflow import Workflow, WorkflowVersion
from app.domain.services.audit_service import AuditService
from app.domain.services.workflow_planner import WorkflowPlan, PlannedNode, PlannedConnection


class WorkflowBuilder:
    """Pure domain workflow builder compiling plans into n8n workflow definitions."""

    # Prohibited secret patterns in node parameters
    PROHIBITED_SECRET_KEYS = {
        "password", "secret", "api_key", "apikey", "access_token",
        "private_key", "client_secret", "bearer"
    }

    def __init__(self, audit_service: Optional[AuditService] = None) -> None:
        self.audit_service = audit_service

    def build_workflow_definition(self, plan: WorkflowPlan) -> Dict[str, Any]:
        """Compile a WorkflowPlan into canonical n8n workflow definition JSON."""
        if not plan.nodes:
            raise InvariantViolationError("Cannot build workflow definition from an empty plan")

        # Map node_id -> node_name and format nodes with 2D grid coordinates
        node_id_to_name: Dict[str, str] = {}
        formatted_nodes: List[Dict[str, Any]] = []

        start_x = 250
        y_pos = 300
        x_spacing = 250

        for i, node in enumerate(plan.nodes):
            node_id_to_name[node.node_id] = node.name
            formatted_node = {
                "id": str(uuid4()),
                "name": node.name,
                "type": node.node_type,
                "typeVersion": node.type_version,
                "position": [start_x + i * x_spacing, y_pos],
                "parameters": dict(node.parameters),
            }
            if node.retry_on_fail:
                formatted_node["retryOnFail"] = True
                formatted_node["maxTries"] = node.max_retries

            formatted_nodes.append(formatted_node)

        # Compile connections adjacency map: connections[source]["main"][out_idx] = [...]
        connections: Dict[str, Dict[str, List[List[Dict[str, Any]]]]] = {}

        for conn in plan.connections:
            source_name = node_id_to_name.get(conn.source_node)
            target_name = node_id_to_name.get(conn.target_node)

            if not source_name or not target_name:
                raise InvariantViolationError(
                    f"Connection references unknown node: '{conn.source_node}' -> '{conn.target_node}'"
                )

            if source_name not in connections:
                connections[source_name] = {"main": []}

            main_outputs = connections[source_name]["main"]
            # Ensure the outer list is large enough for the source_output_index
            while len(main_outputs) <= conn.source_output_index:
                main_outputs.append([])

            main_outputs[conn.source_output_index].append({
                "node": target_name,
                "type": "main",
                "index": conn.target_input_index,
            })

        definition: Dict[str, Any] = {
            "name": plan.workflow_name,
            "nodes": formatted_nodes,
            "connections": connections,
            "settings": {
                "saveDataErrorExecution": "all",
                "saveDataSuccessExecution": "all",
                "saveManualExecutions": True,
                "saveExecutionProgress": True,
                "executionTimeout": 300,
            },
            "meta": {
                "templateCredsSetupCompleted": True,
                "instanceId": "aae-dev",
                "specificationId": str(plan.specification_id),
                "specificationVersion": plan.specification_version,
                "planId": str(plan.plan_id),
            },
        }

        # Validate secret hygiene
        self._validate_no_secrets_in_definition(definition)

        return definition

    def build_workflow(
        self,
        plan: WorkflowPlan,
        project_id: UUID,
        created_by: str = "agent",
        workflow: Optional[Workflow] = None,
        correlation_id: Optional[str] = None,
    ) -> Tuple[Workflow, WorkflowVersion]:
        """Compile a plan and encapsulate it in a domain Workflow and WorkflowVersion."""
        definition = self.build_workflow_definition(plan)

        if workflow is None:
            workflow = Workflow(
                project_id=project_id,
                name=plan.workflow_name,
            )

        # Version spec UUID: generate or reference
        spec_version_uuid = uuid4()
        version = workflow.add_version(
            specification_version_id=spec_version_uuid,
            definition=definition,
            change_reason=f"Compiled from plan {plan.plan_id}",
            created_by=created_by,
        )

        if self.audit_service:
            self.audit_service.record_workflow_mutation(
                mutation_type="built",
                workflow_id=str(workflow.id),
                actor=created_by,
                version_number=version.version_number,
                before_state=None,
                after_state={"name": plan.workflow_name, "node_count": len(plan.nodes)},
                change_reason=f"Compiled from plan {plan.plan_id}",
                correlation_id=correlation_id,
            )

        return workflow, version

    def _validate_no_secrets_in_definition(self, definition: Dict[str, Any]) -> None:
        """Scan node parameters to ensure no raw secrets are committed in workflow definition."""
        nodes = definition.get("nodes", [])
        for node in nodes:
            params = node.get("parameters", {})
            self._scan_dict_for_secrets(node.get("name", "unknown"), params)

    def _scan_dict_for_secrets(self, node_name: str, data: Any) -> None:
        """Recursively scan parameters dictionary for prohibited raw secrets."""
        if isinstance(data, dict):
            for k, v in data.items():
                if any(sec in k.lower() for sec in self.PROHIBITED_SECRET_KEYS):
                    # Check if value appears to be a raw credential rather than an expression or id
                    if isinstance(v, str) and not (v.startswith("={{") and v.endswith("}}")):
                        raise DomainValidationError(
                            f"Prohibited hardcoded secret detected in node '{node_name}' parameter '{k}'. "
                            "Secrets must be managed via credential references, not plaintext."
                        )
                self._scan_dict_for_secrets(node_name, v)
        elif isinstance(data, list):
            for item in data:
                self._scan_dict_for_secrets(node_name, item)
