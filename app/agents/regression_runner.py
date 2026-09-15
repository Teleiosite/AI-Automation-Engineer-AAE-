"""Regression Runner Agent Component (Phase 16).

Agent interface for executing regression suites across repaired workflow versions,
preventing regressions before advancing to deployment.
"""

from typing import List, Optional
from uuid import UUID

from app.domain.models.workflow import Workflow
from app.domain.services.regression_engine import (
    RegressionEngine,
    RegressionResult,
)
from app.domain.services.workflow_test_engine import TestScenario


class RegressionRunner:
    """Agent component responsible for regression testing repaired workflows."""

    def __init__(self, regression_engine: Optional[RegressionEngine] = None) -> None:
        self.engine = regression_engine or RegressionEngine()

    def register_baseline_scenario(
        self,
        workflow_id: UUID,
        scenario: TestScenario,
        is_critical: bool = False,
        covered_nodes: Optional[List[str]] = None,
    ) -> None:
        """Add baseline scenario to workflow's regression catalog."""
        self.engine.register_scenario(
            workflow_id=workflow_id,
            scenario=scenario,
            is_critical=is_critical,
            covered_nodes=covered_nodes,
        )

    def verify_repair(
        self,
        workflow: Workflow,
        version_number: int,
        failing_scenario: TestScenario,
        touched_nodes: Optional[List[str]] = None,
        correlation_id: Optional[str] = None,
    ) -> RegressionResult:
        """Run regression suite against repaired version and verify zero regressions."""
        return self.engine.run_regression(
            workflow=workflow,
            version_number=version_number,
            failing_scenario=failing_scenario,
            touched_nodes=touched_nodes,
            correlation_id=correlation_id,
        )
