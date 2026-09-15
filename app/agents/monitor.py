"""Monitor Agent Component (Phase 18).

Agent interface for operational telemetry, health evaluation, and automatic
escalation of critical failure bursts to the Diagnostician.
"""

from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from app.agents.diagnostician import Diagnostician
from app.domain.models.workflow import Workflow
from app.domain.services.diagnosis_engine import StructuredDiagnosis
from app.domain.services.workflow_monitor import (
    AlertSeverity,
    HealthStatus,
    WorkflowHealthReport,
    WorkflowMonitor,
)


class MonitorAgent:
    """Agent component providing continuous health monitoring and diagnosis routing."""

    def __init__(
        self,
        monitor_service: Optional[WorkflowMonitor] = None,
        diagnostician: Optional[Diagnostician] = None,
    ) -> None:
        self.monitor = monitor_service or WorkflowMonitor()
        self.diagnostician = diagnostician or Diagnostician()

    def record_run(
        self,
        workflow_id: UUID,
        duration_ms: float,
        is_success: bool,
        error_message: Optional[str] = None,
    ) -> None:
        """Record execution metrics."""
        self.monitor.record_execution(
            workflow_id=workflow_id,
            duration_ms=duration_ms,
            is_success=is_success,
            error_message=error_message,
        )

    def check_health(
        self,
        workflow: Workflow,
    ) -> WorkflowHealthReport:
        """Evaluate operational health of a workflow."""
        return self.monitor.evaluate_health(
            workflow_id=workflow.id,
            workflow=workflow,
        )

    def check_and_escalate(
        self,
        workflow: Workflow,
    ) -> Tuple[WorkflowHealthReport, Optional[StructuredDiagnosis]]:
        """Check health and automatically escalate critical alert bursts to Diagnostician."""
        report = self.check_health(workflow)
        diagnosis = None

        critical_alerts = [a for a in report.active_alerts if a.severity == AlertSeverity.CRITICAL]
        if critical_alerts:
            # Route failure details to Diagnostician
            latest_crit = critical_alerts[0]
            cur_ver = workflow.get_current_version()
            diagnosis = self.diagnostician.diagnose_execution(
                execution_data={
                    "error_message": latest_crit.message,
                    "failed_node": workflow.name,
                },
                workflow_id=workflow.id,
                workflow_version_number=cur_ver.version_number if cur_ver else 1,
            )

        return report, diagnosis
