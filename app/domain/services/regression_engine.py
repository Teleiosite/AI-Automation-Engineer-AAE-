"""Regression Engine Service (§14 AAE_AGENT_SPECIFICATION, §18 CODEX_IMPLEMENTATION_PLAN).

Ensures workflow repairs and modifications resolve failures without introducing
regressions, breaking critical baseline capabilities, or causing silent behavioral drift.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
from uuid import UUID, uuid4

from app.domain.errors import DomainValidationError, InvariantViolationError
from app.domain.models.workflow import Workflow, WorkflowVersion
from app.domain.services.audit_service import AuditService
from app.domain.services.workflow_test_engine import (
    TestRunReport,
    TestScenario,
    TestStatus,
    WorkflowTestEngine,
)


@dataclass
class RegressionSuite:
    """Catalog of regression scenarios and node coverage mappings for a specific workflow."""
    workflow_id: UUID
    scenarios: Dict[str, TestScenario] = field(default_factory=dict)
    critical_scenario_names: Set[str] = field(default_factory=set)
    node_coverage: Dict[str, Set[str]] = field(default_factory=dict)  # node_name -> set of scenario_names
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def add_scenario(
        self,
        scenario: TestScenario,
        is_critical: bool = False,
        covered_nodes: Optional[List[str]] = None,
    ) -> None:
        self.scenarios[scenario.name] = scenario
        if is_critical:
            self.critical_scenario_names.add(scenario.name)
        if covered_nodes:
            for node in covered_nodes:
                if node not in self.node_coverage:
                    self.node_coverage[node] = set()
                self.node_coverage[node].add(scenario.name)
        self.updated_at = datetime.now(timezone.utc)


@dataclass(frozen=True)
class RegressionResult:
    """Outcome of regression test execution evaluating a repaired workflow version."""
    workflow_id: UUID
    version_number: int
    repaired_test_passed: bool
    affected_tests_passed: bool
    critical_tests_passed: bool
    total_scenarios_evaluated: int
    all_passed: bool
    drift_detected: bool
    report: TestRunReport
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflow_id": str(self.workflow_id),
            "version_number": self.version_number,
            "repaired_test_passed": self.repaired_test_passed,
            "affected_tests_passed": self.affected_tests_passed,
            "critical_tests_passed": self.critical_tests_passed,
            "total_scenarios_evaluated": self.total_scenarios_evaluated,
            "all_passed": self.all_passed,
            "drift_detected": self.drift_detected,
            "evaluated_at": self.evaluated_at.isoformat(),
            "report": self.report.to_dict(),
        }


# Suppress pytest collection warning on domain dataclass
RegressionResult.__test__ = False


class RegressionEngine:
    """Engine managing regression suites, selective test targeting, and drift detection."""

    def __init__(
        self,
        test_engine: Optional[WorkflowTestEngine] = None,
        audit_service: Optional[AuditService] = None,
    ) -> None:
        self.test_engine = test_engine or WorkflowTestEngine()
        self.audit_service = audit_service
        self._suites: Dict[UUID, RegressionSuite] = {}

    def get_or_create_suite(self, workflow_id: UUID) -> RegressionSuite:
        """Fetch or initialize the regression suite for a workflow."""
        if workflow_id not in self._suites:
            self._suites[workflow_id] = RegressionSuite(workflow_id=workflow_id)
        return self._suites[workflow_id]

    def register_scenario(
        self,
        workflow_id: UUID,
        scenario: TestScenario,
        is_critical: bool = False,
        covered_nodes: Optional[List[str]] = None,
    ) -> None:
        """Register a test scenario into the workflow's regression catalog."""
        suite = self.get_or_create_suite(workflow_id)
        suite.add_scenario(scenario, is_critical=is_critical, covered_nodes=covered_nodes)

    def select_tests_for_repair(
        self,
        workflow_id: UUID,
        failing_scenario: TestScenario,
        touched_nodes: Optional[List[str]] = None,
    ) -> List[TestScenario]:
        """Intelligently assemble the minimal sufficient regression test suite.

        Combines:
        1. Original failing scenario (must now pass).
        2. Component-affected scenarios covering touched nodes.
        3. All critical baseline scenarios.
        """
        suite = self.get_or_create_suite(workflow_id)
        selected_dict: Dict[str, TestScenario] = {}

        # 1. Original failing scenario is mandatory
        selected_dict[failing_scenario.name] = failing_scenario

        # 2. Critical baseline scenarios
        for name in suite.critical_scenario_names:
            if name in suite.scenarios:
                selected_dict[name] = suite.scenarios[name]

        # 3. Affected scenarios covering touched nodes
        if touched_nodes:
            for node in touched_nodes:
                affected_names = suite.node_coverage.get(node, set())
                for sname in affected_names:
                    if sname in suite.scenarios:
                        selected_dict[sname] = suite.scenarios[sname]

        return list(selected_dict.values())

    def run_regression(
        self,
        workflow: Workflow,
        version_number: int,
        failing_scenario: TestScenario,
        touched_nodes: Optional[List[str]] = None,
        correlation_id: Optional[str] = None,
    ) -> RegressionResult:
        """Execute regression verification on a repaired workflow version."""
        target_ver: Optional[WorkflowVersion] = None
        for v in workflow.versions:
            if v.version_number == version_number:
                target_ver = v
                break

        if not target_ver:
            raise InvariantViolationError(f"Target version {version_number} does not exist on workflow {workflow.id}")

        suite = self.get_or_create_suite(workflow.id)
        selected_scenarios = self.select_tests_for_repair(
            workflow_id=workflow.id,
            failing_scenario=failing_scenario,
            touched_nodes=touched_nodes,
        )

        # Run test engine against selected suite
        test_report = self.test_engine.run_tests(
            workflow_id=workflow.id,
            workflow_version_id=target_ver.id,
            definition=target_ver.definition,
            scenarios=selected_scenarios,
            correlation_id=correlation_id,
        )

        # Evaluate individual scenario categories
        repaired_test_passed = False
        critical_tests_passed = True
        affected_tests_passed = True
        drift_detected = False

        result_map = {r.scenario_name: r for r in test_report.results}

        # Check repaired failing scenario
        if failing_scenario.name in result_map:
            repaired_test_passed = (result_map[failing_scenario.name].status == TestStatus.PASS)

        # Check critical scenarios
        for crit_name in suite.critical_scenario_names:
            if crit_name in result_map:
                if result_map[crit_name].status != TestStatus.PASS:
                    critical_tests_passed = False
                    drift_detected = True

        # Check other affected scenarios
        for s in selected_scenarios:
            if s.name != failing_scenario.name and s.name not in suite.critical_scenario_names:
                if s.name in result_map and result_map[s.name].status != TestStatus.PASS:
                    affected_tests_passed = False
                    drift_detected = True

        all_passed = (
            repaired_test_passed and
            critical_tests_passed and
            affected_tests_passed and
            not drift_detected and
            test_report.all_passed
        )

        if self.audit_service:
            self.audit_service.record_workflow_mutation(
                mutation_type="regression_tested",
                workflow_id=str(workflow.id),
                actor="regression_engine",
                version_number=version_number,
                before_state={"repaired_version": version_number},
                after_state={
                    "all_passed": all_passed,
                    "repaired_test_passed": repaired_test_passed,
                    "critical_tests_passed": critical_tests_passed,
                    "drift_detected": drift_detected,
                },
                change_reason=f"Regression suite completed. Status: {'PASS' if all_passed else 'FAIL'}",
                correlation_id=correlation_id,
            )

        return RegressionResult(
            workflow_id=workflow.id,
            version_number=version_number,
            repaired_test_passed=repaired_test_passed,
            affected_tests_passed=affected_tests_passed,
            critical_tests_passed=critical_tests_passed,
            total_scenarios_evaluated=len(selected_scenarios),
            all_passed=all_passed,
            drift_detected=drift_detected,
            report=test_report,
        )
