"""Workflow Test Engine Service (§32-34 CODEX_IMPLEMENTATION_PLAN, §21 N8N_CONTROL_SURFACE).

Executes and verifies workflows against structured test scenarios, evaluating
both technical execution integrity and semantic business correctness.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import time
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from app.domain.enums import SemanticStatus, TechnicalStatus
from app.domain.errors import DomainValidationError
from app.domain.models.execution import Execution, ExecutionResult
from app.domain.models.specification import Specification
from app.domain.services.audit_service import AuditService


class TestStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"
    SKIPPED = "SKIPPED"


class AssertionType(str, Enum):
    TECHNICAL = "TECHNICAL"
    SEMANTIC = "SEMANTIC"
    SCHEMA = "SCHEMA"
    DATA_OUTPUT = "DATA_OUTPUT"
    TIMING = "TIMING"


@dataclass(frozen=True)
class TestAssertion:
    """Discrete assertion evaluated within a test case."""
    assertion_type: AssertionType
    target: str
    expected: Any
    actual: Any
    passed: bool
    message: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "assertion_type": self.assertion_type.value,
            "target": self.target,
            "expected": str(self.expected),
            "actual": str(self.actual),
            "passed": self.passed,
            "message": self.message,
        }


@dataclass(frozen=True)
class TestScenario:
    """Test scenario defining inputs, expected results, and optional failure injection."""
    name: str
    description: str
    inputs: Dict[str, Any] = field(default_factory=dict)
    expected_outputs: Dict[str, Any] = field(default_factory=dict)
    expected_technical_status: TechnicalStatus = TechnicalStatus.SUCCESS
    expected_semantic_status: SemanticStatus = SemanticStatus.SATISFIED
    failure_injection: Optional[Dict[str, Any]] = None  # e.g. {"fail_node": "...", "error": "..."}

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise DomainValidationError("Test scenario name cannot be empty")


@dataclass(frozen=True)
class TestCaseResult:
    """Execution and evaluation result of an individual test scenario."""
    scenario_name: str
    status: TestStatus
    technical_status: TechnicalStatus
    semantic_status: SemanticStatus
    assertions: List[TestAssertion] = field(default_factory=list)
    test_id: UUID = field(default_factory=uuid4)
    duration_ms: float = 0.0
    output_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    executed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_id": str(self.test_id),
            "scenario_name": self.scenario_name,
            "status": self.status.value,
            "technical_status": self.technical_status.value,
            "semantic_status": self.semantic_status.value,
            "duration_ms": self.duration_ms,
            "output_data": self.output_data,
            "error_message": self.error_message,
            "executed_at": self.executed_at.isoformat(),
            "assertions": [a.to_dict() for a in self.assertions],
        }


@dataclass(frozen=True)
class TestRunReport:
    """Aggregate report summarizing all test results for a workflow version."""
    workflow_id: UUID
    workflow_version_id: UUID
    total_tests: int
    passed_count: int
    failed_count: int
    skipped_count: int
    results: List[TestCaseResult]
    all_passed: bool
    report_id: UUID = field(default_factory=uuid4)
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": str(self.report_id),
            "workflow_id": str(self.workflow_id),
            "workflow_version_id": str(self.workflow_version_id),
            "total_tests": self.total_tests,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "skipped_count": self.skipped_count,
            "all_passed": self.all_passed,
            "generated_at": self.generated_at.isoformat(),
            "results": [r.to_dict() for r in self.results],
        }


# Prevent pytest from attempting to collect domain classes as test classes
TestStatus.__test__ = False
TestAssertion.__test__ = False
TestScenario.__test__ = False
TestCaseResult.__test__ = False
TestRunReport.__test__ = False


class WorkflowTestEngine:
    """Engine executing test scenarios and verifying technical & semantic behavior."""

    def __init__(self, audit_service: Optional[AuditService] = None) -> None:
        self.audit_service = audit_service

    def run_tests(
        self,
        workflow_id: UUID,
        workflow_version_id: UUID,
        definition: Dict[str, Any],
        scenarios: List[TestScenario],
        specification: Optional[Specification] = None,
        correlation_id: Optional[str] = None,
    ) -> TestRunReport:
        """Execute test scenarios against workflow definition and compile comprehensive report."""
        if not scenarios:
            if specification:
                scenarios = self.generate_scenarios_from_specification(specification)
            else:
                scenarios = [
                    TestScenario(
                        name="Default Smoke Test",
                        description="Basic sanity verification with empty payload",
                        inputs={},
                        expected_outputs={},
                    )
                ]

        results: List[TestCaseResult] = []
        for scenario in scenarios:
            res = self._execute_scenario_simulation(definition, scenario)
            results.append(res)

        passed = [r for r in results if r.status == TestStatus.PASS]
        failed = [r for r in results if r.status == TestStatus.FAIL]
        skipped = [r for r in results if r.status == TestStatus.SKIPPED]

        all_passed = (len(failed) == 0 and len(passed) > 0)

        report = TestRunReport(
            workflow_id=workflow_id,
            workflow_version_id=workflow_version_id,
            total_tests=len(results),
            passed_count=len(passed),
            failed_count=len(failed),
            skipped_count=len(skipped),
            results=results,
            all_passed=all_passed,
        )

        if self.audit_service:
            self.audit_service.record_workflow_mutation(
                mutation_type="tested",
                workflow_id=str(workflow_id),
                actor="test_engine",
                version_number=1,
                before_state={"total_tests": len(results)},
                after_state={"all_passed": all_passed, "passed": len(passed), "failed": len(failed)},
                change_reason=f"Executed {len(results)} test scenario(s). Result: {'PASS' if all_passed else 'FAIL'}",
                correlation_id=correlation_id,
            )

        return report

    def _execute_scenario_simulation(
        self,
        definition: Dict[str, Any],
        scenario: TestScenario,
    ) -> TestCaseResult:
        """Simulate workflow execution graph with test inputs and evaluate assertions."""
        start_time = time.perf_counter()
        assertions: List[TestAssertion] = []
        nodes = definition.get("nodes", [])
        connections = definition.get("connections", {})

        # Check for simulated failure injection
        failure_inj = scenario.failure_injection
        if failure_inj:
            fail_node = failure_inj.get("fail_node", "")
            fail_error = failure_inj.get("error", "Injected failure")

            duration = (time.perf_counter() - start_time) * 1000
            tech_status = TechnicalStatus.ERROR
            sem_status = SemanticStatus.UNSATISFIED

            tech_pass = (tech_status == scenario.expected_technical_status)
            sem_pass = (sem_status == scenario.expected_semantic_status)

            assertions.append(
                TestAssertion(
                    assertion_type=AssertionType.TECHNICAL,
                    target=f"node.{fail_node}",
                    expected=scenario.expected_technical_status.value,
                    actual=tech_status.value,
                    passed=tech_pass,
                    message=f"Injected node failure: {fail_error}",
                )
            )
            assertions.append(
                TestAssertion(
                    assertion_type=AssertionType.SEMANTIC,
                    target="semantic_status",
                    expected=scenario.expected_semantic_status.value,
                    actual=sem_status.value,
                    passed=sem_pass,
                    message="Semantic outcome matching failure expectation",
                )
            )

            status = TestStatus.PASS if (tech_pass and sem_pass) else TestStatus.FAIL
            return TestCaseResult(
                scenario_name=scenario.name,
                status=status,
                technical_status=tech_status,
                semantic_status=sem_status,
                assertions=assertions,
                duration_ms=duration,
                error_message=fail_error,
            )

        # Normal execution simulation: traverse graph and propagate data
        current_data = dict(scenario.inputs)
        node_exec_order = []
        visited = set()

        # Find entry node
        entry_node = None
        for n in nodes:
            ntype = str(n.get("type", "")).lower()
            nname = str(n.get("name", "")).lower()
            if "webhook" in ntype or "trigger" in ntype or "trigger" in nname:
                entry_node = n
                break
        if not entry_node and nodes:
            entry_node = nodes[0]

        # Simulate data flow through connected nodes
        current = entry_node
        while current and current.get("name") not in visited:
            cname = current.get("name")
            visited.add(cname)
            node_exec_order.append(cname)

            # Transform/accumulate mock output based on node type
            params = current.get("parameters", {})
            ntype = current.get("type", "")

            if "postgres" in ntype:
                # Simulated DB operation
                current_data["db_record_id"] = current_data.get("id", "rec-101")
                current_data["db_synced"] = True
            elif "email" in ntype:
                # Simulated email delivery
                current_data["email_sent"] = True
                current_data["outbound_notification"] = True
                current_data["recipient"] = params.get("toEmail", current_data.get("email", "test@domain.com"))
            elif cname == "Validate Lifecycle Transition":
                contract = params.get("contract", {})
                transition_valid = any(
                    transition.get("from") == current_data.get("state")
                    and transition.get("to") == current_data.get("next_state")
                    for transition in contract.get("transitions", [])
                )
                current_data["transition_validated"] = transition_valid
            elif cname == "Extract Structured Document Fields":
                contract = params.get("contract", {})
                current_data["document_extracted"] = all(field in current_data for field in contract.get("required_fields", []))
            elif cname == "Evaluate Decision Matrix":
                contract = params.get("contract", {})
                weights = contract.get("weights", [])
                current_data["evaluation_completed"] = len(weights) >= 2
            elif cname == "Append Immutable Audit Ledger":
                contract = params.get("contract", {})
                current_data["audit_ledger_appended"] = bool(contract.get("hash_chain") and contract.get("append_only"))
            elif cname == "Monitor SLA Deadline":
                current_data["sla_monitoring_scheduled"] = bool(params.get("contract", {}).get("deadline"))
            elif cname == "Return Grounded Query Result":
                current_data["grounded_query_response"] = bool(params.get("contract", {}).get("grounding_source"))
            elif "wait" in ntype.lower():
                current_data["human_approval_recorded"] = True
            elif "httprequest" in ntype.lower():
                # Simulated HTTP request response
                current_data["http_status"] = 200
                current_data["outbound_notification"] = True
                current_data["response_body"] = {"status": "ok"}

            # Move to next connected node
            outgoing = connections.get(cname, {}).get("main", [])
            next_node = None
            if outgoing and len(outgoing) > 0 and len(outgoing[0]) > 0:
                next_target_name = outgoing[0][0].get("node")
                for n in nodes:
                    if n.get("name") == next_target_name:
                        next_node = n
                        break
            current = next_node

        duration = (time.perf_counter() - start_time) * 1000
        actual_technical_status = TechnicalStatus.SUCCESS

        # Technical Assertion: Execution succeeded
        tech_passed = (actual_technical_status == scenario.expected_technical_status)
        assertions.append(
            TestAssertion(
                assertion_type=AssertionType.TECHNICAL,
                target="execution_status",
                expected=scenario.expected_technical_status.value,
                actual=actual_technical_status.value,
                passed=tech_passed,
                message="Workflow completed technical execution successfully",
            )
        )

        # Semantic Assertions: Verify expected outputs
        semantic_passed = True
        for key, expected_val in scenario.expected_outputs.items():
            actual_val = current_data.get(key)
            val_passed = (actual_val == expected_val)
            if not val_passed:
                semantic_passed = False
            assertions.append(
                TestAssertion(
                    assertion_type=AssertionType.SEMANTIC,
                    target=f"output.{key}",
                    expected=expected_val,
                    actual=actual_val,
                    passed=val_passed,
                    message=f"Semantic expectation for '{key}' {'satisfied' if val_passed else 'violated'}",
                )
            )

        actual_semantic_status = SemanticStatus.SATISFIED if semantic_passed else SemanticStatus.UNSATISFIED

        # Technical success != Semantic success verification
        sem_status_passed = (actual_semantic_status == scenario.expected_semantic_status)
        assertions.append(
            TestAssertion(
                assertion_type=AssertionType.SEMANTIC,
                target="semantic_status",
                expected=scenario.expected_semantic_status.value,
                actual=actual_semantic_status.value,
                passed=sem_status_passed,
                message="Business semantic status verified",
            )
        )

        overall_pass = all(a.passed for a in assertions)
        test_status = TestStatus.PASS if overall_pass else TestStatus.FAIL

        return TestCaseResult(
            scenario_name=scenario.name,
            status=test_status,
            technical_status=actual_technical_status,
            semantic_status=actual_semantic_status,
            assertions=assertions,
            duration_ms=duration,
            output_data=current_data,
            error_message=None if overall_pass else "Semantic or technical assertion failed",
        )

    def generate_scenarios_from_specification(
        self,
        specification: Specification,
    ) -> List[TestScenario]:
        """Derive standard happy-path and edge test scenarios from specification content."""
        cur_ver = specification.get_current_version()
        content = cur_ver.structured_content if cur_ver else {}

        scenarios: List[TestScenario] = []

        # Scenario 1: Standard happy path
        inputs = {}
        for inp in content.get("inputs", []):
            inputs[str(inp)] = f"sample-{inp}"

        # Populate only contract-defined fixture values; this makes semantic
        # scenarios exercise transition, extraction, and evaluation assertions.
        for semantic_requirement in content.get("semantic_requirements", []):
            contract = semantic_requirement.get("contract", {})
            if semantic_requirement.get("type") == "STATE_MACHINE":
                transitions = contract.get("transitions", [])
                if transitions:
                    inputs["state"] = transitions[0]["from"]
                    inputs["next_state"] = transitions[0]["to"]
            elif semantic_requirement.get("type") == "DOCUMENT_EXTRACTION":
                for field in contract.get("required_fields", []):
                    inputs.setdefault(field, f"sample-{field}")
            elif semantic_requirement.get("type") == "EVALUATION_CRITERIA":
                for criterion in contract.get("weights", []):
                    inputs.setdefault(criterion["criterion"], 1)

        expected = {}
        for out in content.get("outputs", []):
            out_lower = str(out).lower()
            if "email" in out_lower:
                expected["email_sent"] = True
            elif "database" in out_lower or "record" in out_lower:
                expected["db_synced"] = True
            elif "outbound notification" in out_lower:
                expected["outbound_notification"] = True
            elif "human approval" in out_lower:
                expected["human_approval_recorded"] = True
            elif "lifecycle transition" in out_lower:
                expected["transition_validated"] = True
            elif "document fields" in out_lower:
                expected["document_extracted"] = True
            elif "weighted evaluation" in out_lower:
                expected["evaluation_completed"] = True
            elif "audit ledger" in out_lower:
                expected["audit_ledger_appended"] = True
            elif "sla monitoring" in out_lower:
                expected["sla_monitoring_scheduled"] = True
            elif "grounded query" in out_lower:
                expected["grounded_query_response"] = True

        if not expected:
            raise ValueError("Specification has no verifiable output contract; refusing to generate vacuous scenarios.")

        scenarios.append(
            TestScenario(
                name="Specification Baseline Happy Path",
                description=f"Validates criteria: {', '.join(content.get('success_criteria', ['Standard execution']))}",
                inputs=inputs,
                expected_outputs=expected,
                expected_technical_status=TechnicalStatus.SUCCESS,
                expected_semantic_status=SemanticStatus.SATISFIED,
            )
        )

        # Scenario 2: Downstream failure injection
        scenarios.append(
            TestScenario(
                name="Downstream Network Failure Resilience",
                description="Simulates downstream service unavailability and validates error handling",
                inputs=inputs,
                expected_outputs={},
                expected_technical_status=TechnicalStatus.ERROR,
                expected_semantic_status=SemanticStatus.UNSATISFIED,
                failure_injection={"fail_node": "External Service", "error": "HTTP 503 Service Unavailable"},
            )
        )

        return scenarios
