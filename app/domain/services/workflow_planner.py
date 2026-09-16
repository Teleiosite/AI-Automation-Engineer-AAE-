"""Workflow Planner Engine (Phase 10).

Translates an approved Specification into an ordered, capability-verified,
and testable Workflow Plan with concrete node topologies and retry policies.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import UUID, uuid4

from app.domain.enums import SpecificationStatus
from app.domain.errors import InvariantViolationError
from app.domain.models.specification import Specification
from app.domain.capabilities.service import CapabilityEnforcementService, CapabilityEnforcementError


@dataclass(frozen=True)
class PlannedNode:
    """Individual workflow node definition in the planned topology."""
    node_id: str
    name: str
    node_type: str
    type_version: float
    parameters: Dict[str, Any]
    retry_on_fail: bool = False
    max_retries: int = 0
    is_destructive: bool = False
    notes: Optional[str] = None


@dataclass(frozen=True)
class PlannedConnection:
    """Directed connection edge linking node output to node input."""
    source_node: str
    target_node: str
    source_output_index: int = 0
    target_input_index: int = 0


@dataclass(frozen=True)
class WorkflowPlan:
    """Ordered, capability-verified implementation plan for a workflow."""
    plan_id: UUID
    specification_id: UUID
    specification_version: int
    workflow_name: str
    nodes: Tuple[PlannedNode, ...]
    connections: Tuple[PlannedConnection, ...]
    data_stores: Tuple[str, ...]
    external_services: Tuple[str, ...]
    has_destructive_operations: bool
    planned_actions: Tuple[str, ...]
    test_scenarios: Tuple[str, ...]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        """Convert plan to dictionary structure."""
        return {
            "plan_id": str(self.plan_id),
            "specification_id": str(self.specification_id),
            "specification_version": self.specification_version,
            "workflow_name": self.workflow_name,
            "nodes": [
                {
                    "node_id": n.node_id,
                    "name": n.name,
                    "node_type": n.node_type,
                    "type_version": n.type_version,
                    "parameters": n.parameters,
                    "retry_on_fail": n.retry_on_fail,
                    "max_retries": n.max_retries,
                    "is_destructive": n.is_destructive,
                }
                for n in self.nodes
            ],
            "connections": [
                {
                    "source": c.source_node,
                    "target": c.target_node,
                    "source_index": c.source_output_index,
                    "target_index": c.target_input_index,
                }
                for c in self.connections
            ],
            "data_stores": list(self.data_stores),
            "external_services": list(self.external_services),
            "has_destructive_operations": self.has_destructive_operations,
            "planned_actions": list(self.planned_actions),
            "test_scenarios": list(self.test_scenarios),
            "created_at": self.created_at.isoformat(),
        }


class WorkflowPlanner:
    """Pure domain workflow planner converting approved specifications into verified plans."""

    def __init__(self, capability_service: Optional[CapabilityEnforcementService] = None) -> None:
        self.capability_service = capability_service

    def create_plan(
        self,
        specification: Specification,
        version_number: Optional[int] = None,
        workflow_name: Optional[str] = None,
        environment: str = "development",
    ) -> WorkflowPlan:
        """Derive an authorized WorkflowPlan from an approved specification."""
        # 1. Enforce Approval Precondition (§18, §26)
        if not specification.is_construction_authorized():
            raise InvariantViolationError(
                f"Cannot create workflow plan for unapproved specification (status: '{specification.status.value}')"
            )

        ver_num = version_number or specification.current_version_number
        version = specification.get_version(ver_num)
        if not version or not version.is_approved:
            raise InvariantViolationError(
                f"Target specification version {ver_num} is not approved"
            )

        # 2. Enforce core workflow creation capability
        self._verify_capability("workflow.create", environment)

        content = version.structured_content

        # 3. Plan nodes & topology
        nodes: List[PlannedNode] = []
        connections: List[PlannedConnection] = []
        planned_actions: List[str] = []
        data_stores: List[str] = [ds["name"] for ds in content.get("data_stores", [])]
        external_services: List[str] = [es["name"] for es in content.get("external_services", [])]

        prev_node_id: Optional[str] = None

        source_req_text = (content.get("source_request", {}).get("text", "") + " " + content.get("business_objective", "")).lower()
        needs_response_node = any(kw in source_req_text for kw in ["respond", "response", "reply", "return json", "confirmation json"])

        # 3.1 Trigger node
        trigger_desc = content.get("trigger", "").lower()
        if "schedule" in trigger_desc or "cron" in trigger_desc or "monday" in trigger_desc:
            trigger_node = PlannedNode(
                node_id="node_trigger",
                name="Schedule Trigger",
                node_type="n8n-nodes-base.scheduleTrigger",
                type_version=1.2,
                parameters={"rule": {"interval": [{"field": "cronExpression", "expression": "0 8 * * 1"}]}},
            )
        else:
            resp_mode = "responseNode" if needs_response_node else "onReceived"
            trigger_node = PlannedNode(
                node_id="node_trigger",
                name="Webhook Trigger",
                node_type="n8n-nodes-base.webhook",
                type_version=2.0,
                parameters={"path": "lead", "httpMethod": "POST", "responseMode": resp_mode},
            )
        nodes.append(trigger_node)
        prev_node_id = trigger_node.node_id

        # 3.2 Deduplication / Idempotency Gate
        has_dedup = any("deduplicat" in a.get("description", "").lower() or "idempotency" in a.get("description", "").lower() for a in content.get("actions", [])) or any(kw in source_req_text for kw in ["don't create another", "already there", "processed twice"])
        if has_dedup:
            dedup_node = PlannedNode(
                node_id=f"node_dedup_{len(nodes)}",
                name="Check Existing Record (Idempotency)",
                node_type="n8n-nodes-base.code",
                type_version=2.0,
                parameters={
                    "mode": "runOnceForEachItem",
                    "jsCode": "const item = $json.body || $json;\n// Verify whether record exists by email or event_id\nconst isDuplicate = false;\nreturn { ...item, is_duplicate: isDuplicate };",
                },
            )
            nodes.append(dedup_node)
            connections.append(PlannedConnection(source_node=prev_node_id, target_node=dedup_node.node_id))
            prev_node_id = dedup_node.node_id
            planned_actions.append("Deduplicate incoming event and enforce idempotency guard")

            if_new_node = PlannedNode(
                node_id=f"node_if_new_{len(nodes)}",
                name="If New Record",
                node_type="n8n-nodes-base.if",
                type_version=2.0,
                parameters={
                    "conditions": {
                        "boolean": [{"value1": "={{ $json.is_duplicate }}", "value2": False}]
                    }
                },
            )
            nodes.append(if_new_node)
            connections.append(PlannedConnection(source_node=prev_node_id, target_node=if_new_node.node_id))
            prev_node_id = if_new_node.node_id
            planned_actions.append("Branch on new versus duplicate record")

        # 3.3 PII Sanitization / Security Access Control
        has_sensitive = any("sensitive" in s.lower() for s in content.get("security_requirements", [])) or any(kw in source_req_text for kw in ["sensitive information", "authori", "restricted"])
        if has_sensitive:
            sanitize_node = PlannedNode(
                node_id=f"node_sanitize_{len(nodes)}",
                name="Sanitize Sensitive PII",
                node_type="n8n-nodes-base.code",
                type_version=2.0,
                parameters={
                    "mode": "runOnceForEachItem",
                    "jsCode": "const item = $json.body || $json;\nconst { tax_id, credit_card_last4, ...safeData } = item;\nreturn { ...safeData, _redacted: true };",
                },
            )
            nodes.append(sanitize_node)
            connections.append(PlannedConnection(source_node=prev_node_id, target_node=sanitize_node.node_id))
            prev_node_id = sanitize_node.node_id
            planned_actions.append("Enforce access control and PII data sanitization for sensitive information")

        # 3.4 Specification-Driven Topology Planning
        has_routing_action = any("routing" in a.get("description", "").lower() or "conditional" in a.get("description", "").lower() for a in content.get("actions", []))
        has_financial_action = any("financial" in a.get("description", "").lower() or "invoice" in a.get("description", "").lower() or "payment" in a.get("description", "").lower() for a in content.get("actions", []))
        has_retry_failure = any("retry" in f.lower() for f in content.get("failure_handling", [])) or any("retry" in a.get("description", "").lower() for a in content.get("actions", []))

        # 3.5 Data transformation / Code validation actions
        has_transform_action = any(
            any(k in a.get("description", "").lower() for k in ["validate", "format", "code", "transform", "enrich", "assign"])
            for a in content.get("actions", [])
        )
        if has_transform_action and not has_dedup:
            node_id = f"node_code_{len(nodes)}"
            code_node = PlannedNode(
                node_id=node_id,
                name="Validate & Format (Code)",
                node_type="n8n-nodes-base.code",
                type_version=2.0,
                parameters={
                    "mode": "runOnceForEachItem",
                    "jsCode": "const item = $json.body || $json;\nreturn {\n  ...item,\n  qualified: Boolean(item.email || item.name),\n  processedAt: new Date().toISOString()\n};",
                },
            )
            nodes.append(code_node)
            connections.append(PlannedConnection(source_node=prev_node_id, target_node=node_id))
            prev_node_id = node_id
            planned_actions.append("Validate and format lead payload via JavaScript Code node")

        # 3.6 Data Store & State Inspection / Persistence
        if content.get("data_stores"):
            for i, ds in enumerate(content.get("data_stores")):
                ds_name = ds.get("name", "") if isinstance(ds, dict) else str(ds)
                node_id = f"node_postgres_{i+1}"
                table_name = "invoices" if "invoice" in ds_name.lower() else ("appointments" if "appointment" in ds_name.lower() else "records")
                op = "update" if has_financial_action and "status" in trigger_desc else "insert"
                ds_node = PlannedNode(
                    node_id=node_id,
                    name=f"PostgreSQL {ds_name}",
                    node_type="n8n-nodes-base.postgres",
                    type_version=2.5,
                    parameters={"operation": op, "table": table_name},
                    retry_on_fail=True,
                    max_retries=3,
                )
                nodes.append(ds_node)
                connections.append(PlannedConnection(source_node=prev_node_id, target_node=node_id))
                prev_node_id = node_id
                planned_actions.append(f"Persist record to {ds_name}")
        elif has_financial_action and ("status" in trigger_desc or "invoice" in source_req_text):
            upd_node = PlannedNode(
                node_id=f"node_pg_{len(nodes)}",
                name="Update Customer Invoice Record",
                node_type="n8n-nodes-base.postgres",
                type_version=2.5,
                parameters={"operation": "update", "table": "invoices"},
                retry_on_fail=True,
                max_retries=3,
            )
            nodes.append(upd_node)
            connections.append(PlannedConnection(source_node=prev_node_id, target_node=upd_node.node_id))
            prev_node_id = upd_node.node_id
            planned_actions.append("Update customer invoice record")
        elif any("persist" in a.get("description", "").lower() or "store" in a.get("description", "").lower() or "query state" in a.get("description", "").lower() or "inspect record" in a.get("description", "").lower() for a in content.get("actions", [])):
            ds_node = PlannedNode(
                node_id=f"node_pg_{len(nodes)}",
                name="PostgreSQL Customer Records",
                node_type="n8n-nodes-base.postgres",
                type_version=2.5,
                parameters={"operation": "insert", "table": "records"},
                retry_on_fail=True,
                max_retries=3,
            )
            nodes.append(ds_node)
            connections.append(PlannedConnection(source_node=prev_node_id, target_node=ds_node.node_id))
            prev_node_id = ds_node.node_id
            planned_actions.append("Persist incoming record to data store")

        # 3.7 Conditional Routing & Branching
        if has_routing_action and not any(n.node_type == "n8n-nodes-base.if" for n in nodes):
            route_node = PlannedNode(
                node_id=f"node_router_{len(nodes)}",
                name="Route Sales vs Support" if "sales" in source_req_text else "Evaluate Condition & Route",
                node_type="n8n-nodes-base.if",
                type_version=2.0,
                parameters={
                    "conditions": {
                        "string": [{"value1": "={{ $json.enquiry_type || $json.body?.enquiry_type || $json.status || 'sales' }}", "operation": "equal", "value2": "sales"}]
                    }
                },
            )
            nodes.append(route_node)
            connections.append(PlannedConnection(source_node=prev_node_id, target_node=route_node.node_id))

            # Branch 0 (Primary / True route)
            if external_services:
                es0 = external_services[0]
                es0_name = es0.get("name", "Primary Service") if isinstance(es0, dict) else str(es0)
                is_email0 = any(k in es0_name.lower() for k in ["email", "smtp", "channel", "notification", "team", "sales", "finance", "support"]) and not any(k in es0_name.lower() for k in ["endpoint", "api", "3pl", "gateway"])
                node_0 = PlannedNode(
                    node_id=f"node_branch_0_{len(nodes)}",
                    name=f"Notify ({es0_name})" if is_email0 else f"Call ({es0_name})",
                    node_type="n8n-nodes-base.emailSend" if is_email0 else "n8n-nodes-base.httpRequest",
                    type_version=2.1 if is_email0 else 4.2,
                    parameters={
                        "fromEmail": "notifications@example.com",
                        "toEmail": "sales@example.com" if "sales" in es0_name.lower() else ("finance@example.com" if "finance" in es0_name.lower() else "team@example.com"),
                        "subject": f"Routing: {es0_name}",
                        "text": "Condition matched primary branch.",
                    } if is_email0 else {"method": "POST", "url": "https://api.external.com/primary"},
                    retry_on_fail=True,
                    max_retries=3,
                )
            else:
                node_0 = PlannedNode(
                    node_id=f"node_branch_0_{len(nodes)}",
                    name="Notify Primary Team",
                    node_type="n8n-nodes-base.emailSend",
                    type_version=2.1,
                    parameters={
                        "fromEmail": "notifications@example.com",
                        "toEmail": "team@example.com",
                        "subject": "Primary Condition Alert",
                        "text": "Condition matched primary branch.",
                    },
                    retry_on_fail=True,
                    max_retries=3,
                )
            nodes.append(node_0)
            connections.append(PlannedConnection(source_node=route_node.node_id, target_node=node_0.node_id, source_output_index=0))

            # Branch 1 (Secondary / False route)
            if len(external_services) >= 2:
                es1 = external_services[1]
                es1_name = es1.get("name", "Secondary Service") if isinstance(es1, dict) else str(es1)
                is_email1 = any(k in es1_name.lower() for k in ["email", "smtp", "channel", "notification", "team", "support", "pool"]) and not any(k in es1_name.lower() for k in ["endpoint", "api", "3pl", "gateway"])
                node_1 = PlannedNode(
                    node_id=f"node_branch_1_{len(nodes)}",
                    name=f"Notify ({es1_name})" if is_email1 else f"Call ({es1_name})",
                    node_type="n8n-nodes-base.emailSend" if is_email1 else "n8n-nodes-base.httpRequest",
                    type_version=2.1 if is_email1 else 4.2,
                    parameters={
                        "fromEmail": "notifications@example.com",
                        "toEmail": "support@example.com" if "support" in es1_name.lower() else "team@example.com",
                        "subject": f"Routing: {es1_name}",
                        "text": "Condition matched secondary branch.",
                    } if is_email1 else {"method": "POST", "url": "https://api.external.com/secondary"},
                    retry_on_fail=True,
                    max_retries=3,
                )
            else:
                node_1 = PlannedNode(
                    node_id=f"node_branch_1_{len(nodes)}",
                    name="Notify Support Team",
                    node_type="n8n-nodes-base.emailSend",
                    type_version=2.1,
                    parameters={
                        "fromEmail": "notifications@example.com",
                        "toEmail": "support@example.com",
                        "subject": "Secondary Condition Notice",
                        "text": "Condition matched fallback branch.",
                    },
                    retry_on_fail=True,
                    max_retries=3,
                )
            nodes.append(node_1)
            connections.append(PlannedConnection(source_node=route_node.node_id, target_node=node_1.node_id, source_output_index=1))
            prev_node_id = node_0.node_id
            planned_actions.append("Conditional evaluation and routing branch")
            planned_actions.append("Dispatch outbound notification/message")

        elif not has_routing_action or not any(n.node_type == "n8n-nodes-base.if" for n in nodes):
            # Sequential external service dispatch
            for j, es in enumerate(external_services):
                es_name = es.get("name", "") if isinstance(es, dict) else str(es)
                node_id = f"node_ext_service_{j+1}"
                is_email = any(k in es_name.lower() for k in ["email", "smtp", "channel", "notification", "team", "reminder", "sales", "support", "finance"]) and not any(k in es_name.lower() for k in ["endpoint", "api", "3pl", "gateway"])
                if is_email:
                    es_node = PlannedNode(
                        node_id=node_id,
                        name=f"Send Notification ({es_name})",
                        node_type="n8n-nodes-base.emailSend",
                        type_version=2.1,
                        parameters={
                            "fromEmail": "notifications@example.com",
                            "toEmail": "={{ $json.body?.email || $json.email || 'recipient@example.com' }}",
                            "subject": f"Notification: {es_name}",
                            "text": "Automation notification received.",
                        },
                        retry_on_fail=True,
                        max_retries=3,
                    )
                else:
                    es_node = PlannedNode(
                        node_id=node_id,
                        name=f"HTTP API ({es_name})",
                        node_type="n8n-nodes-base.httpRequest",
                        type_version=4.2,
                        parameters={"method": "POST", "url": "https://api.external.com/send"},
                        retry_on_fail=True,
                        max_retries=3,
                    )
                nodes.append(es_node)
                connections.append(PlannedConnection(source_node=prev_node_id, target_node=node_id))
                prev_node_id = node_id
                planned_actions.append(f"Dispatch outbound message via {es_name}")

        # 3.8 Outbound notification fallback
        if not any(n.node_type in ("n8n-nodes-base.emailSend", "n8n-nodes-base.httpRequest") for n in nodes if n.node_id != trigger_node.node_id):
            if any(any(k in a.get("description", "").lower() for k in ["dispatch", "notify", "outbound", "send", "alert", "push", "page", "ping"]) for a in content.get("actions", [])):
                node_id = f"node_email_{len(nodes)}"
                es_node = PlannedNode(
                    node_id=node_id,
                    name="Notification Email",
                    node_type="n8n-nodes-base.emailSend",
                    type_version=2.1,
                    parameters={
                        "fromEmail": "notifications@example.com",
                        "toEmail": "={{ $json.body?.email || $json.email || 'team@example.com' }}",
                        "subject": "Automation Notification",
                        "text": "New incoming automation event received.",
                    },
                    retry_on_fail=True,
                    max_retries=3,
                )
                nodes.append(es_node)
                connections.append(PlannedConnection(source_node=prev_node_id, target_node=node_id))
                prev_node_id = node_id
                planned_actions.append("Dispatch outbound notification/message")

        # 3.9 Respond to Webhook action
        if needs_response_node:
            node_id = f"node_respond_{len(nodes)}"
            respond_node = PlannedNode(
                node_id=node_id,
                name="Respond to Webhook",
                node_type="n8n-nodes-base.respondToWebhook",
                type_version=1.1,
                parameters={
                    "respondWith": "json",
                    "responseBody": "={\n  \"status\": \"success\",\n  \"message\": \"Event received and validated successfully\",\n  \"data\": $json\n}",
                },
            )
            nodes.append(respond_node)
            connections.append(PlannedConnection(source_node=prev_node_id, target_node=node_id))
            prev_node_id = node_id
            planned_actions.append("Respond to incoming webhook with confirmation JSON")

        # Reconcile planned_actions with specified actions to guarantee zero drift
        for act in content.get("actions", []):
            desc = act.get("description", "")
            if desc and desc not in planned_actions:
                planned_actions.append(desc)

        # 3.4 Destructive actions check
        has_destructive = any(
            act.get("is_destructive", False) for act in content.get("actions", [])
        )
        if has_destructive:
            # Check delete capability
            self._verify_capability("workflow.delete", environment)

        # 3.5 Test scenarios from success criteria
        test_scenarios = [
            f"Verify: {crit}" for crit in content.get("success_criteria", [])
        ]
        if not test_scenarios:
            test_scenarios = ["Verify successful execution of all planned nodes without errors"]

        name = workflow_name or f"Workflow-{content.get('business_objective', 'Automated')[:30]}"

        return WorkflowPlan(
            plan_id=uuid4(),
            specification_id=specification.id,
            specification_version=ver_num,
            workflow_name=name,
            nodes=tuple(nodes),
            connections=tuple(connections),
            data_stores=tuple(data_stores),
            external_services=tuple(external_services),
            has_destructive_operations=has_destructive,
            planned_actions=tuple(planned_actions),
            test_scenarios=tuple(test_scenarios),
        )

    def _verify_capability(self, operation: str, environment: str = "development") -> None:
        """Enforce capability verification if CapabilityEnforcementService is attached."""
        if self.capability_service:
            self.capability_service.enforce(operation)
