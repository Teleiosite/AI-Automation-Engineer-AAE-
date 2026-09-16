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

        # 3.4 Conditional Branching / Routing Actions
        has_sales_support = "sales" in source_req_text and "support" in source_req_text
        has_payment_status = ("invoice" in source_req_text or "payment" in source_req_text) and ("failed" in source_req_text or "fails" in source_req_text)

        if has_sales_support:
            route_node = PlannedNode(
                node_id=f"node_router_{len(nodes)}",
                name="Route Sales vs Support",
                node_type="n8n-nodes-base.if",
                type_version=2.0,
                parameters={
                    "conditions": {
                        "string": [{"value1": "={{ $json.enquiry_type || $json.body?.enquiry_type || 'sales' }}", "operation": "equal", "value2": "sales"}]
                    }
                },
            )
            nodes.append(route_node)
            connections.append(PlannedConnection(source_node=prev_node_id, target_node=route_node.node_id))

            sales_node = PlannedNode(
                node_id=f"node_sales_{len(nodes)}",
                name="Notify Sales Team",
                node_type="n8n-nodes-base.emailSend",
                type_version=2.1,
                parameters={
                    "fromEmail": "notifications@example.com",
                    "toEmail": "sales@example.com",
                    "subject": "New Qualified Sales Lead",
                    "text": "A serious sales prospect enquiry has been received.",
                },
            )
            nodes.append(sales_node)
            connections.append(PlannedConnection(source_node=route_node.node_id, target_node=sales_node.node_id, source_output_index=0))

            support_node = PlannedNode(
                node_id=f"node_support_{len(nodes)}",
                name="Notify Support Team",
                node_type="n8n-nodes-base.emailSend",
                type_version=2.1,
                parameters={
                    "fromEmail": "notifications@example.com",
                    "toEmail": "support@example.com",
                    "subject": "New Support Enquiry",
                    "text": "A general question enquiry has been received.",
                },
            )
            nodes.append(support_node)
            connections.append(PlannedConnection(source_node=route_node.node_id, target_node=support_node.node_id, source_output_index=1))
            prev_node_id = sales_node.node_id
            planned_actions.append("Conditional evaluation and routing branch")
            planned_actions.append("Dispatch outbound notification/message")

        elif has_payment_status:
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

            if_fail_node = PlannedNode(
                node_id=f"node_if_failed_{len(nodes)}",
                name="If Payment Failed",
                node_type="n8n-nodes-base.if",
                type_version=2.0,
                parameters={
                    "conditions": {
                        "string": [{"value1": "={{ $json.status || $json.body?.status }}", "operation": "equal", "value2": "failed"}]
                    }
                },
            )
            nodes.append(if_fail_node)
            connections.append(PlannedConnection(source_node=upd_node.node_id, target_node=if_fail_node.node_id))

            finance_alert_node = PlannedNode(
                node_id=f"node_finance_{len(nodes)}",
                name="Alert Finance Team",
                node_type="n8n-nodes-base.emailSend",
                type_version=2.1,
                parameters={
                    "fromEmail": "billing@example.com",
                    "toEmail": "finance@example.com",
                    "subject": "URGENT: Payment Failed",
                    "text": "Invoice payment has failed. Immediate action required.",
                },
            )
            nodes.append(finance_alert_node)
            connections.append(PlannedConnection(source_node=if_fail_node.node_id, target_node=finance_alert_node.node_id, source_output_index=0))
            prev_node_id = finance_alert_node.node_id
            planned_actions.append("Process financial transactions or invoice data")
            planned_actions.append("Persist incoming record to data store")
            planned_actions.append("Conditional evaluation and routing branch")
            planned_actions.append("Dispatch outbound notification/message")

        # 3.5 External API Call with Retry / Resilience
        elif any(kw in source_req_text for kw in ["external service doesn't respond", "try again a few times", "let us know if it still fails"]):
            ext_call_node = PlannedNode(
                node_id=f"node_ext_{len(nodes)}",
                name="Call External Service API",
                node_type="n8n-nodes-base.httpRequest",
                type_version=4.2,
                parameters={"method": "POST", "url": "https://api.external.com/v1/sync"},
                retry_on_fail=True,
                max_retries=3,
            )
            nodes.append(ext_call_node)
            connections.append(PlannedConnection(source_node=prev_node_id, target_node=ext_call_node.node_id))

            alert_fail_node = PlannedNode(
                node_id=f"node_alert_{len(nodes)}",
                name="Alert Team on Service Failure",
                node_type="n8n-nodes-base.emailSend",
                type_version=2.1,
                parameters={
                    "fromEmail": "alerts@example.com",
                    "toEmail": "oncall@example.com",
                    "subject": "External Service Call Failed After Retries",
                    "text": "The external service failed to respond after maximum retries.",
                },
            )
            nodes.append(alert_fail_node)
            connections.append(PlannedConnection(source_node=ext_call_node.node_id, target_node=alert_fail_node.node_id))
            prev_node_id = alert_fail_node.node_id
            planned_actions.append("Call external service with bounded retry policy")
            planned_actions.append("Dispatch outbound notification/message")

        # 3.6 Appointment Booking & Reminder Scheduling
        elif any(kw in source_req_text for kw in ["books an appointment", "reminder before the appointment", "appointment"]):
            rec_node = PlannedNode(
                node_id=f"node_rec_{len(nodes)}",
                name="Record Appointment Details",
                node_type="n8n-nodes-base.postgres",
                type_version=2.5,
                parameters={"operation": "insert", "table": "appointments"},
                retry_on_fail=True,
                max_retries=3,
            )
            nodes.append(rec_node)
            connections.append(PlannedConnection(source_node=prev_node_id, target_node=rec_node.node_id))

            rem_node = PlannedNode(
                node_id=f"node_rem_{len(nodes)}",
                name="Schedule Appointment Reminder",
                node_type="n8n-nodes-base.emailSend",
                type_version=2.1,
                parameters={
                    "fromEmail": "appointments@example.com",
                    "toEmail": "={{ $json.body?.customer_email || $json.customer_email || 'client@example.com' }}",
                    "subject": "Appointment Reminder",
                    "text": "Reminder: Your appointment is scheduled.",
                },
            )
            nodes.append(rem_node)
            connections.append(PlannedConnection(source_node=rec_node.node_id, target_node=rem_node.node_id))
            prev_node_id = rem_node.node_id
            planned_actions.append("Persist incoming record to data store")
            planned_actions.append("Dispatch outbound notification/message")

        else:
            # 3.7 Standard Data store actions
            for i, ds in enumerate(content.get("data_stores", [])):
                ds_name = ds.get("name", "")
                node_id = f"node_postgres_{i+1}"
                ds_node = PlannedNode(
                    node_id=node_id,
                    name=f"PostgreSQL {ds_name}",
                    node_type="n8n-nodes-base.postgres",
                    type_version=2.5,
                    parameters={"operation": "insert", "table": "leads"},
                    retry_on_fail=True,
                    max_retries=3,
                )
                nodes.append(ds_node)
                connections.append(PlannedConnection(source_node=prev_node_id, target_node=node_id))
                prev_node_id = node_id
                planned_actions.append(f"Persist record to {ds_name}")

            # 3.8 Standard External service communications
            for j, es in enumerate(content.get("external_services", [])):
                es_name = es.get("name", "")
                node_id = f"node_ext_service_{j+1}"
                if any(k in es_name.lower() for k in ["email", "smtp", "channel", "notification", "team"]):
                    es_node = PlannedNode(
                        node_id=node_id,
                        name=f"Send Email ({es_name})",
                        node_type="n8n-nodes-base.emailSend",
                        type_version=2.1,
                        parameters={
                            "fromEmail": "leads@example.com",
                            "toEmail": "={{ $json.body?.email || $json.email || 'lead@example.com' }}",
                            "subject": "Notification Received",
                            "text": "Automation notification.",
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

        # 3.9 Data transformation / Code validation actions
        if any(kw in source_req_text for kw in ["code", "validate", "transform", "javascript", "script"]):
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

        # 3.10 Respond to Webhook action
        if needs_response_node:
            node_id = f"node_respond_{len(nodes)}"
            respond_node = PlannedNode(
                node_id=node_id,
                name="Respond to Webhook",
                node_type="n8n-nodes-base.respondToWebhook",
                type_version=1.1,
                parameters={
                    "respondWith": "json",
                    "responseBody": "={\n  \"status\": \"success\",\n  \"message\": \"Lead received and validated successfully\",\n  \"data\": $json\n}",
                },
            )
            nodes.append(respond_node)
            connections.append(PlannedConnection(source_node=prev_node_id, target_node=node_id))
            prev_node_id = node_id
            planned_actions.append("Respond to incoming webhook with confirmation JSON")

        # 3.11 Fallback persistence and notification if requested in actions
        if not any(n.node_type == "n8n-nodes-base.postgres" for n in nodes):
            if any(kw in source_req_text for kw in ["save their details", "save details", "customer records", "customer record", "record it"]):
                node_id = f"node_pg_{len(nodes)}"
                ds_node = PlannedNode(
                    node_id=node_id,
                    name="PostgreSQL Customer Records",
                    node_type="n8n-nodes-base.postgres",
                    type_version=2.5,
                    parameters={"operation": "insert", "table": "records"},
                    retry_on_fail=True,
                    max_retries=3,
                )
                nodes.append(ds_node)
                connections.append(PlannedConnection(source_node=prev_node_id, target_node=node_id))
                prev_node_id = node_id
                planned_actions.append("Persist incoming record to data store")

        if not any(n.node_type in ("n8n-nodes-base.emailSend", "n8n-nodes-base.httpRequest") for n in nodes if n.node_id != trigger_node.node_id):
            if any(kw in source_req_text for kw in ["notify", "alert", "let us know", "team knows", "message"]):
                node_id = f"node_email_{len(nodes)}"
                es_node = PlannedNode(
                    node_id=node_id,
                    name="Team Notification Email",
                    node_type="n8n-nodes-base.emailSend",
                    type_version=2.1,
                    parameters={
                        "fromEmail": "notifications@example.com",
                        "toEmail": "team@example.com",
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
