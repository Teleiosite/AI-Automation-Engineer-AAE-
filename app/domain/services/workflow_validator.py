"""Workflow Validator Service (§20-21 N8N_CONTROL_SURFACE, §29-31 CODEX_IMPLEMENTATION_PLAN).

Provides independent, deterministic, multi-layer validation of workflow definitions:
- Schema validation
- Structural graph validation
- Node and connection validation
- Configuration completeness validation
- Expression syntax validation
- Security & secret hygiene validation
- Requirement mapping & semantic correctness
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import re
from typing import Any, Dict, List, Optional, Set

from app.domain.models.specification import Specification
from app.domain.services.workflow_planner import WorkflowPlan


class ValidationSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class ValidationCategory(str, Enum):
    SCHEMA = "SCHEMA"
    STRUCTURE = "STRUCTURE"
    NODE = "NODE"
    CONNECTION = "CONNECTION"
    CONFIGURATION = "CONFIGURATION"
    EXPRESSION = "EXPRESSION"
    SECURITY = "SECURITY"
    REQUIREMENT_MAPPING = "REQUIREMENT_MAPPING"
    SEMANTIC = "SEMANTIC"


@dataclass(frozen=True)
class ValidationIssue:
    """Represents a discrete validation finding."""
    rule_id: str
    category: ValidationCategory
    severity: ValidationSeverity
    message: str
    node_name: Optional[str] = None
    field: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "category": self.category.value,
            "severity": self.severity.value,
            "message": self.message,
            "node_name": self.node_name,
            "field": self.field,
        }


@dataclass(frozen=True)
class ValidationReport:
    """Comprehensive validation outcome for a candidate workflow definition."""
    is_valid: bool
    workflow_name: str
    issues: List[ValidationIssue] = field(default_factory=list)
    error_count: int = 0
    warning_count: int = 0
    critical_count: int = 0
    validated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def has_errors(self) -> bool:
        return self.error_count > 0 or self.critical_count > 0

    def has_critical(self) -> bool:
        return self.critical_count > 0

    def get_issues_by_category(self, category: ValidationCategory) -> List[ValidationIssue]:
        return [i for i in self.issues if i.category == category]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "workflow_name": self.workflow_name,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "critical_count": self.critical_count,
            "validated_at": self.validated_at,
            "issues": [i.to_dict() for i in self.issues],
        }


class WorkflowValidator:
    """Pure domain validation engine evaluating workflows prior to execution/deployment."""

    PROHIBITED_SECRET_KEYS: Set[str] = {
        "password",
        "secret",
        "api_key",
        "apikey",
        "token",
        "bearer",
        "auth",
        "private_key",
    }

    TRIGGER_TYPES: Set[str] = {
        "n8n-nodes-base.webhook",
        "n8n-nodes-base.scheduleTrigger",
        "n8n-nodes-base.manualTrigger",
        "n8n-nodes-base.cron",
        "n8n-nodes-base.interval",
    }

    DESTRUCTIVE_SQL_PATTERNS = [
        re.compile(r"\bDROP\s+(TABLE|DATABASE|SCHEMA|VIEW)\b", re.IGNORECASE),
        re.compile(r"\bTRUNCATE\s+(TABLE)?\b", re.IGNORECASE),
        re.compile(r"\bDELETE\s+FROM\s+\w+\s*(;|$)", re.IGNORECASE),  # Unbounded DELETE without WHERE
    ]

    def validate(
        self,
        definition: Any,
        specification: Optional[Specification] = None,
        plan: Optional[WorkflowPlan] = None,
    ) -> ValidationReport:
        """Run all technical, security, and semantic validation checks on a workflow definition."""
        issues: List[ValidationIssue] = []

        # 1. Schema Validation
        if not isinstance(definition, dict):
            issues.append(
                ValidationIssue(
                    rule_id="SCH-001",
                    category=ValidationCategory.SCHEMA,
                    severity=ValidationSeverity.CRITICAL,
                    message="Workflow definition root must be a JSON/dict object.",
                )
            )
            return self._build_report("unknown", issues)

        workflow_name = str(definition.get("name", "Unnamed Workflow"))

        if "nodes" not in definition or not isinstance(definition["nodes"], list):
            issues.append(
                ValidationIssue(
                    rule_id="SCH-002",
                    category=ValidationCategory.SCHEMA,
                    severity=ValidationSeverity.CRITICAL,
                    message="Workflow definition must contain a 'nodes' list.",
                    field="nodes",
                )
            )
            return self._build_report(workflow_name, issues)

        if "connections" not in definition or not isinstance(definition["connections"], dict):
            issues.append(
                ValidationIssue(
                    rule_id="SCH-003",
                    category=ValidationCategory.SCHEMA,
                    severity=ValidationSeverity.CRITICAL,
                    message="Workflow definition must contain a 'connections' dictionary.",
                    field="connections",
                )
            )

        nodes: List[Dict[str, Any]] = definition.get("nodes", [])
        connections: Dict[str, Any] = definition.get("connections", {})

        # Validate each individual node schema
        node_names: Set[str] = set()
        node_ids: Set[str] = set()

        for idx, node in enumerate(nodes):
            if not isinstance(node, dict):
                issues.append(
                    ValidationIssue(
                        rule_id="SCH-004",
                        category=ValidationCategory.SCHEMA,
                        severity=ValidationSeverity.ERROR,
                        message=f"Node at index {idx} must be a dictionary.",
                    )
                )
                continue

            node_name = node.get("name")
            if not node_name or not isinstance(node_name, str):
                issues.append(
                    ValidationIssue(
                        rule_id="SCH-005",
                        category=ValidationCategory.SCHEMA,
                        severity=ValidationSeverity.ERROR,
                        message=f"Node at index {idx} has missing or non-string name.",
                        field="name",
                    )
                )
            else:
                if node_name in node_names:
                    issues.append(
                        ValidationIssue(
                            rule_id="STR-001",
                            category=ValidationCategory.STRUCTURE,
                            severity=ValidationSeverity.ERROR,
                            message=f"Duplicate node name '{node_name}'. Node names must be unique for expression referencing.",
                            node_name=node_name,
                        )
                    )
                node_names.add(node_name)

            node_id = node.get("id")
            if node_id:
                if str(node_id) in node_ids:
                    issues.append(
                        ValidationIssue(
                            rule_id="STR-002",
                            category=ValidationCategory.STRUCTURE,
                            severity=ValidationSeverity.ERROR,
                            message=f"Duplicate node id '{node_id}'.",
                            node_name=node_name or str(idx),
                        )
                    )
                node_ids.add(str(node_id))

            node_type = node.get("type")
            if not node_type or not isinstance(node_type, str):
                issues.append(
                    ValidationIssue(
                        rule_id="NOD-001",
                        category=ValidationCategory.NODE,
                        severity=ValidationSeverity.ERROR,
                        message=f"Node '{node_name or idx}' must specify a valid string type.",
                        node_name=node_name,
                        field="type",
                    )
                )

            type_version = node.get("typeVersion")
            if type_version is None or not isinstance(type_version, (int, float)) or type_version <= 0:
                issues.append(
                    ValidationIssue(
                        rule_id="NOD-002",
                        category=ValidationCategory.NODE,
                        severity=ValidationSeverity.ERROR,
                        message=f"Node '{node_name or idx}' has invalid typeVersion '{type_version}'. Must be positive number.",
                        node_name=node_name,
                        field="typeVersion",
                    )
                )

        # 2. Structural Graph Validation
        self._validate_structure(nodes, connections, issues)

        # 3. Connection Endpoint & Topology Validation
        self._validate_connections(nodes, connections, issues)

        # 4. Configuration Completeness
        self._validate_configurations(nodes, issues)

        # 5. Expression Syntax Validation
        self._validate_expressions(nodes, issues)

        # 6. Security Hygiene & Secret Scanning
        self._validate_security(nodes, issues)

        # 7. Requirement Mapping & Semantic Validation
        if specification or plan:
            self._validate_semantic_alignment(nodes, specification, plan, issues)

        return self._build_report(workflow_name, issues)

    def _validate_structure(
        self,
        nodes: List[Dict[str, Any]],
        connections: Dict[str, Any],
        issues: List[ValidationIssue],
    ) -> None:
        """Validate workflow topology, trigger presence, and unreachable nodes."""
        if not nodes:
            issues.append(
                ValidationIssue(
                    rule_id="STR-003",
                    category=ValidationCategory.STRUCTURE,
                    severity=ValidationSeverity.CRITICAL,
                    message="Workflow must contain at least one node.",
                )
            )
            return

        # Check trigger presence
        trigger_nodes = [
            n for n in nodes
            if self._is_trigger_node(n)
        ]

        if not trigger_nodes:
            issues.append(
                ValidationIssue(
                    rule_id="STR-004",
                    category=ValidationCategory.STRUCTURE,
                    severity=ValidationSeverity.ERROR,
                    message="Workflow lacks an entry trigger node (e.g. Webhook, ScheduleTrigger).",
                )
            )

        # Map incoming and outgoing connections per node
        incoming_counts: Dict[str, int] = {n.get("name", ""): 0 for n in nodes if n.get("name")}
        outgoing_counts: Dict[str, int] = {n.get("name", ""): 0 for n in nodes if n.get("name")}

        for src, conn_types in connections.items():
            if not isinstance(conn_types, dict):
                continue
            for out_type, outputs in conn_types.items():
                if not isinstance(outputs, list):
                    continue
                for output_idx_conns in outputs:
                    if not isinstance(output_idx_conns, list):
                        continue
                    for edge in output_idx_conns:
                        if isinstance(edge, dict) and "node" in edge:
                            target = edge["node"]
                            outgoing_counts[src] = outgoing_counts.get(src, 0) + 1
                            incoming_counts[target] = incoming_counts.get(target, 0) + 1

        # Check for disconnected/orphaned nodes when > 1 node exists
        if len(nodes) > 1:
            for n in nodes:
                name = n.get("name")
                if not name:
                    continue
                is_trigger = self._is_trigger_node(n)
                in_count = incoming_counts.get(name, 0)
                out_count = outgoing_counts.get(name, 0)

                # Isolated completely
                if in_count == 0 and out_count == 0:
                    issues.append(
                        ValidationIssue(
                            rule_id="STR-005",
                            category=ValidationCategory.STRUCTURE,
                            severity=ValidationSeverity.ERROR,
                            message=f"Node '{name}' is completely disconnected (0 incoming, 0 outgoing).",
                            node_name=name,
                        )
                    )
                # Non-trigger orphan (unreachable)
                elif not is_trigger and in_count == 0:
                    issues.append(
                        ValidationIssue(
                            rule_id="STR-006",
                            category=ValidationCategory.STRUCTURE,
                            severity=ValidationSeverity.ERROR,
                            message=f"Non-trigger node '{name}' has no incoming connections and is unreachable.",
                            node_name=name,
                        )
                    )

    def _validate_connections(
        self,
        nodes: List[Dict[str, Any]],
        connections: Dict[str, Any],
        issues: List[ValidationIssue],
    ) -> None:
        """Validate connection endpoints, self-loops, and target integrity."""
        valid_node_names = {n.get("name") for n in nodes if n.get("name")}
        trigger_node_names = {n.get("name") for n in nodes if n.get("name") and self._is_trigger_node(n)}

        for src_name, conn_types in connections.items():
            if src_name not in valid_node_names:
                issues.append(
                    ValidationIssue(
                        rule_id="CON-001",
                        category=ValidationCategory.CONNECTION,
                        severity=ValidationSeverity.ERROR,
                        message=f"Connection source '{src_name}' does not exist in nodes.",
                        node_name=src_name,
                    )
                )
                continue

            if not isinstance(conn_types, dict):
                issues.append(
                    ValidationIssue(
                        rule_id="CON-002",
                        category=ValidationCategory.CONNECTION,
                        severity=ValidationSeverity.ERROR,
                        message=f"Connections for source '{src_name}' must be a dictionary mapping output types.",
                        node_name=src_name,
                    )
                )
                continue

            for out_type, outputs in conn_types.items():
                if not isinstance(outputs, list):
                    continue
                for out_idx, target_list in enumerate(outputs):
                    if not isinstance(target_list, list):
                        continue
                    for edge in target_list:
                        if not isinstance(edge, dict):
                            issues.append(
                                ValidationIssue(
                                    rule_id="CON-003",
                                    category=ValidationCategory.CONNECTION,
                                    severity=ValidationSeverity.ERROR,
                                    message=f"Connection edge from '{src_name}' must be an object.",
                                    node_name=src_name,
                                )
                            )
                            continue

                        target_name = edge.get("node")
                        if not target_name or target_name not in valid_node_names:
                            issues.append(
                                ValidationIssue(
                                    rule_id="CON-004",
                                    category=ValidationCategory.CONNECTION,
                                    severity=ValidationSeverity.ERROR,
                                    message=f"Connection target '{target_name}' referenced from '{src_name}' does not exist in nodes.",
                                    node_name=src_name,
                                )
                            )

                        # Self loop prevention
                        if target_name == src_name:
                            issues.append(
                                ValidationIssue(
                                    rule_id="CON-005",
                                    category=ValidationCategory.CONNECTION,
                                    severity=ValidationSeverity.ERROR,
                                    message=f"Illegal self-loop detected: node '{src_name}' connects to itself.",
                                    node_name=src_name,
                                )
                            )

                        # Trigger node receiving input
                        if target_name in trigger_node_names:
                            issues.append(
                                ValidationIssue(
                                    rule_id="CON-006",
                                    category=ValidationCategory.CONNECTION,
                                    severity=ValidationSeverity.WARNING,
                                    message=f"Trigger node '{target_name}' should not receive inbound connection from '{src_name}'.",
                                    node_name=target_name,
                                )
                            )

    def _validate_configurations(
        self,
        nodes: List[Dict[str, Any]],
        issues: List[ValidationIssue],
    ) -> None:
        """Validate required configuration parameters per node type."""
        for node in nodes:
            name = node.get("name", "unknown")
            ntype = node.get("type", "")
            params = node.get("parameters", {})

            if not isinstance(params, dict):
                issues.append(
                    ValidationIssue(
                        rule_id="CFG-001",
                        category=ValidationCategory.CONFIGURATION,
                        severity=ValidationSeverity.ERROR,
                        message=f"Node '{name}' parameters must be a dictionary.",
                        node_name=name,
                        field="parameters",
                    )
                )
                continue

            # Webhook node configuration
            if ntype == "n8n-nodes-base.webhook":
                path = params.get("path")
                if not path or not isinstance(path, str) or path.strip() == "":
                    issues.append(
                        ValidationIssue(
                            rule_id="CFG-002",
                            category=ValidationCategory.CONFIGURATION,
                            severity=ValidationSeverity.ERROR,
                            message=f"Webhook node '{name}' missing required 'path' parameter.",
                            node_name=name,
                            field="parameters.path",
                        )
                    )

            # HttpRequest node configuration
            elif ntype == "n8n-nodes-base.httpRequest":
                url = params.get("url")
                if not url or not isinstance(url, str) or url.strip() == "":
                    issues.append(
                        ValidationIssue(
                            rule_id="CFG-003",
                            category=ValidationCategory.CONFIGURATION,
                            severity=ValidationSeverity.ERROR,
                            message=f"HTTP Request node '{name}' missing required 'url' parameter.",
                            node_name=name,
                            field="parameters.url",
                        )
                    )

            # Postgres node configuration
            elif ntype == "n8n-nodes-base.postgres":
                operation = params.get("operation")
                if not operation:
                    issues.append(
                        ValidationIssue(
                            rule_id="CFG-004",
                            category=ValidationCategory.CONFIGURATION,
                            severity=ValidationSeverity.ERROR,
                            message=f"Postgres node '{name}' missing required 'operation' parameter.",
                            node_name=name,
                            field="parameters.operation",
                        )
                    )

            # ScheduleTrigger configuration
            elif ntype == "n8n-nodes-base.scheduleTrigger":
                rule = params.get("rule")
                if not rule and not params.get("interval"):
                    issues.append(
                        ValidationIssue(
                            rule_id="CFG-005",
                            category=ValidationCategory.CONFIGURATION,
                            severity=ValidationSeverity.ERROR,
                            message=f"Schedule Trigger '{name}' missing recurrence rule or interval configuration.",
                            node_name=name,
                            field="parameters.rule",
                        )
                    )

    def _validate_expressions(
        self,
        nodes: List[Dict[str, Any]],
        issues: List[ValidationIssue],
    ) -> None:
        """Scan parameter values for syntax correctness in n8n expressions."""
        for node in nodes:
            name = node.get("name", "unknown")
            params = node.get("parameters", {})
            self._scan_for_malformed_expressions(name, params, issues)

    def _scan_for_malformed_expressions(
        self,
        node_name: str,
        data: Any,
        issues: List[ValidationIssue],
        prefix: str = "parameters",
    ) -> None:
        """Recursively inspect parameter values for unclosed or illegal expression syntax."""
        if isinstance(data, dict):
            for k, v in data.items():
                self._scan_for_malformed_expressions(node_name, v, issues, f"{prefix}.{k}")
        elif isinstance(data, list):
            for i, v in enumerate(data):
                self._scan_for_malformed_expressions(node_name, v, issues, f"{prefix}[{i}]")
        elif isinstance(data, str):
            if "{{" in data or "}}" in data:
                open_count = data.count("{{")
                close_count = data.count("}}")
                if open_count != close_count:
                    issues.append(
                        ValidationIssue(
                            rule_id="EXP-001",
                            category=ValidationCategory.EXPRESSION,
                            severity=ValidationSeverity.ERROR,
                            message=f"Malformed expression with unbalanced braces in node '{node_name}' ({open_count} open, {close_count} close).",
                            node_name=node_name,
                            field=prefix,
                        )
                    )
                # Check for empty expression
                if re.search(r"\{\{\s*\}\}", data):
                    issues.append(
                        ValidationIssue(
                            rule_id="EXP-002",
                            category=ValidationCategory.EXPRESSION,
                            severity=ValidationSeverity.ERROR,
                            message=f"Empty expression '{{{{}}}}' detected in node '{node_name}'.",
                            node_name=node_name,
                            field=prefix,
                        )
                    )

    def _validate_security(
        self,
        nodes: List[Dict[str, Any]],
        issues: List[ValidationIssue],
    ) -> None:
        """Scan parameters for raw hardcoded secrets, insecure protocols, and dangerous queries."""
        for node in nodes:
            name = node.get("name", "unknown")
            params = node.get("parameters", {})
            self._scan_node_security(name, params, issues)

    def _scan_node_security(
        self,
        node_name: str,
        data: Any,
        issues: List[ValidationIssue],
        prefix: str = "parameters",
    ) -> None:
        """Recursively scan node data for security vulnerabilities."""
        if isinstance(data, dict):
            for k, v in data.items():
                field_path = f"{prefix}.{k}"
                # Secret scanning
                if any(sec in k.lower() for sec in self.PROHIBITED_SECRET_KEYS):
                    if isinstance(v, str) and not (v.startswith("={{") and v.endswith("}}")):
                        # Check if it's a non-empty plaintext secret
                        if len(v.strip()) > 0:
                            issues.append(
                                ValidationIssue(
                                    rule_id="SEC-001",
                                    category=ValidationCategory.SECURITY,
                                    severity=ValidationSeverity.CRITICAL,
                                    message=f"Prohibited plaintext secret in parameter '{k}'. Secrets must use credential references or expressions.",
                                    node_name=node_name,
                                    field=field_path,
                                )
                            )

                # Insecure protocol scanning
                if k.lower() in ("url", "uri", "endpoint") and isinstance(v, str):
                    if v.startswith("http://") and not ("localhost" in v or "127.0.0.1" in v):
                        issues.append(
                            ValidationIssue(
                                rule_id="SEC-002",
                                category=ValidationCategory.SECURITY,
                                severity=ValidationSeverity.WARNING,
                                message=f"Insecure plaintext HTTP protocol used for remote URL '{v}'.",
                                node_name=node_name,
                                field=field_path,
                            )
                        )

                # Destructive SQL scanning
                if isinstance(v, str):
                    for pattern in self.DESTRUCTIVE_SQL_PATTERNS:
                        if pattern.search(v):
                            issues.append(
                                ValidationIssue(
                                    rule_id="SEC-003",
                                    category=ValidationCategory.SECURITY,
                                    severity=ValidationSeverity.CRITICAL,
                                    message=f"Destructive or unbounded SQL pattern detected: '{pattern.pattern}'.",
                                    node_name=node_name,
                                    field=field_path,
                                )
                            )

                self._scan_node_security(node_name, v, issues, field_path)
        elif isinstance(data, list):
            for i, v in enumerate(data):
                self._scan_node_security(node_name, v, issues, f"{prefix}[{i}]")

    def _validate_semantic_alignment(
        self,
        nodes: List[Dict[str, Any]],
        specification: Optional[Specification],
        plan: Optional[WorkflowPlan],
        issues: List[ValidationIssue],
    ) -> None:
        """Verify that workflow matches approved specification requirements and planned topology."""
        node_types = {n.get("type") for n in nodes if n.get("type")}
        node_names = {n.get("name") for n in nodes if n.get("name")}

        if specification:
            cur_ver = specification.get_current_version()
            content = cur_ver.structured_content if cur_ver else {}
            trigger = str(content.get("trigger", "")).lower()
            has_schedule = any("scheduletype" in str(n).lower() or "scheduletrigger" in str(n).lower() for n in node_types)
            has_webhook = any("webhook" in str(n).lower() for n in node_types)

            if ("cron" in trigger or "schedule" in trigger or "every" in trigger) and not has_schedule:
                issues.append(
                    ValidationIssue(
                        rule_id="SEM-001",
                        category=ValidationCategory.REQUIREMENT_MAPPING,
                        severity=ValidationSeverity.ERROR,
                        message=f"Specification requires scheduled trigger ('{trigger}'), but workflow lacks ScheduleTrigger node.",
                    )
                )

            if ("webhook" in trigger or "event" in trigger or "http" in trigger) and not has_webhook and not has_schedule:
                issues.append(
                    ValidationIssue(
                        rule_id="SEM-002",
                        category=ValidationCategory.REQUIREMENT_MAPPING,
                        severity=ValidationSeverity.ERROR,
                        message=f"Specification requires event trigger ('{trigger}'), but workflow lacks Webhook trigger node.",
                    )
                )

            # Check external systems coverage
            ext_systems = content.get("external_systems", [])
            for ext in ext_systems:
                ext_lower = str(ext).lower()
                if "postgres" in ext_lower or "database" in ext_lower:
                    if not any("postgres" in str(t).lower() for t in node_types):
                        issues.append(
                            ValidationIssue(
                                rule_id="SEM-003",
                                category=ValidationCategory.SEMANTIC,
                                severity=ValidationSeverity.ERROR,
                                message=f"Specification requires external system '{ext}', but workflow lacks matching Postgres node.",
                            )
                        )
                elif "email" in ext_lower:
                    if not any("email" in str(t).lower() or "smtp" in str(t).lower() for t in node_types):
                        issues.append(
                            ValidationIssue(
                                rule_id="SEM-004",
                                category=ValidationCategory.SEMANTIC,
                                severity=ValidationSeverity.ERROR,
                                message=f"Specification requires email integration ('{ext}'), but workflow lacks email node.",
                            )
                        )

        if plan:
            # Check that planned nodes exist
            for pnode in plan.nodes:
                if pnode.name not in node_names:
                    issues.append(
                        ValidationIssue(
                            rule_id="SEM-005",
                            category=ValidationCategory.REQUIREMENT_MAPPING,
                            severity=ValidationSeverity.ERROR,
                            message=f"Planned node '{pnode.name}' ({pnode.node_type}) missing from built workflow.",
                            node_name=pnode.name,
                        )
                    )

    def _is_trigger_node(self, node: Dict[str, Any]) -> bool:
        """Determine if a node is an event/schedule trigger."""
        ntype = str(node.get("type") or "")
        name = str(node.get("name") or "").lower()
        if ntype in self.TRIGGER_TYPES:
            return True
        if "trigger" in ntype.lower() or "trigger" in name:
            return True
        return False

    def _build_report(self, workflow_name: str, issues: List[ValidationIssue]) -> ValidationReport:
        """Assemble deterministic validation summary report."""
        errors = [i for i in issues if i.severity == ValidationSeverity.ERROR]
        criticals = [i for i in issues if i.severity == ValidationSeverity.CRITICAL]
        warnings = [i for i in issues if i.severity == ValidationSeverity.WARNING]

        is_valid = (len(errors) == 0 and len(criticals) == 0)

        return ValidationReport(
            is_valid=is_valid,
            workflow_name=workflow_name,
            issues=issues,
            error_count=len(errors),
            warning_count=len(warnings),
            critical_count=len(criticals),
        )
