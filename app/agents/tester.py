"""Workflow Tester Agent Component (Phase 13).

Agent interface for executing technical and semantic test scenarios
and verifying workflow readiness prior to deployment approval.
"""

from typing import Any, Dict, List, Optional
from uuid import UUID

from app.domain.enums import WorkflowVersionStatus
from app.domain.errors import InvariantViolationError
from app.domain.models.specification import Specification
from app.domain.models.workflow import Workflow, WorkflowVersion
from app.domain.services.workflow_test_engine import (
    TestRunReport,
    TestScenario,
    WorkflowTestEngine,
)


class Tester:
    """Agent component executing test suites against workflows."""
    __test__ = False

    def __init__(self, test_engine: Optional[WorkflowTestEngine] = None) -> None:
        self.test_engine = test_engine or WorkflowTestEngine()

    def test(
        self,
        workflow_id: UUID,
        workflow_version_id: UUID,
        definition: Dict[str, Any],
        scenarios: Optional[List[TestScenario]] = None,
        specification: Optional[Specification] = None,
        correlation_id: Optional[str] = None,
    ) -> TestRunReport:
        """Run test scenarios against a workflow definition."""
        return self.test_engine.run_tests(
            workflow_id=workflow_id,
            workflow_version_id=workflow_version_id,
            definition=definition,
            scenarios=scenarios or [],
            specification=specification,
            correlation_id=correlation_id,
        )

    def test_workflow(
        self,
        workflow: Workflow,
        version_number: Optional[int] = None,
        scenarios: Optional[List[TestScenario]] = None,
        specification: Optional[Specification] = None,
        correlation_id: Optional[str] = None,
    ) -> TestRunReport:
        """Run test scenarios against a Workflow aggregate version and promote state if passed."""
        if version_number is not None:
            target_version: Optional[WorkflowVersion] = None
            for v in workflow.versions:
                if v.version_number == version_number:
                    target_version = v
                    break
        else:
            target_version = workflow.get_current_version()

        if not target_version:
            raise InvariantViolationError(f"No version found to test on workflow {workflow.id}")

        report = self.test_engine.run_tests(
            workflow_id=workflow.id,
            workflow_version_id=target_version.id,
            definition=target_version.definition,
            scenarios=scenarios or [],
            specification=specification,
            correlation_id=correlation_id,
        )

        # If all tests pass and version is VALIDATED, transition to TESTED
        if report.all_passed and target_version.status == WorkflowVersionStatus.VALIDATED:
            target_version.mark_tested()

        return report
