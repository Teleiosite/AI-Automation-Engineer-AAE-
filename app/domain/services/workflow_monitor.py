"""Workflow Operational Health & Telemetry Monitor (§18 AAE_AGENT_SPECIFICATION, §20 CODEX_IMPLEMENTATION_PLAN).

Tracks execution outcomes, measures latency SLA percentiles, detects failure bursts,
evaluates component health, and issues deterministic operational alerts.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import math
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from app.domain.enums import WorkflowStatus
from app.domain.models.workflow import Workflow
from app.domain.services.audit_service import AuditService


class HealthStatus(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"
    UNKNOWN = "UNKNOWN"


class AlertSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class MonitoringAlert:
    """Actionable alert generated when operational thresholds are breached."""
    workflow_id: UUID
    severity: AlertSeverity
    title: str
    message: str
    trigger_metric: str
    threshold: float
    actual_value: float
    alert_id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_id": str(self.alert_id),
            "workflow_id": str(self.workflow_id),
            "severity": self.severity.value,
            "title": self.title,
            "message": self.message,
            "trigger_metric": self.trigger_metric,
            "threshold": self.threshold,
            "actual_value": self.actual_value,
            "created_at": self.created_at.isoformat(),
        }


@dataclass(frozen=True)
class HealthCheckResult:
    """Discrete status evaluation of a subsystem or component."""
    component: str
    status: HealthStatus
    message: str
    latency_ms: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "component": self.component,
            "status": self.status.value,
            "message": self.message,
            "latency_ms": self.latency_ms,
            "details": self.details,
            "checked_at": self.checked_at.isoformat(),
        }


@dataclass(frozen=True)
class WorkflowHealthReport:
    """Aggregated operational health and performance assessment for a workflow."""
    workflow_id: UUID
    overall_status: HealthStatus
    total_executions: int
    success_rate: float
    failure_rate: float
    average_duration_ms: float
    p95_duration_ms: float
    active_alerts: List[MonitoringAlert] = field(default_factory=list)
    health_checks: List[HealthCheckResult] = field(default_factory=list)
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflow_id": str(self.workflow_id),
            "overall_status": self.overall_status.value,
            "total_executions": self.total_executions,
            "success_rate": self.success_rate,
            "failure_rate": self.failure_rate,
            "average_duration_ms": self.average_duration_ms,
            "p95_duration_ms": self.p95_duration_ms,
            "evaluated_at": self.evaluated_at.isoformat(),
            "active_alerts": [a.to_dict() for a in self.active_alerts],
            "health_checks": [h.to_dict() for h in self.health_checks],
        }


class WorkflowMonitor:
    """Domain service collecting telemetry and monitoring operational health."""

    def __init__(
        self,
        audit_service: Optional[AuditService] = None,
        failure_rate_warn_threshold: float = 0.10,
        failure_rate_crit_threshold: float = 0.25,
        p95_latency_threshold_ms: float = 5000.0,
    ) -> None:
        self.audit_service = audit_service
        self.failure_rate_warn_threshold = failure_rate_warn_threshold
        self.failure_rate_crit_threshold = failure_rate_crit_threshold
        self.p95_latency_threshold_ms = p95_latency_threshold_ms
        self._telemetry: Dict[UUID, List[Dict[str, Any]]] = {}

    def record_execution(
        self,
        workflow_id: UUID,
        duration_ms: float,
        is_success: bool,
        error_message: Optional[str] = None,
    ) -> None:
        """Record an individual execution outcome."""
        if workflow_id not in self._telemetry:
            self._telemetry[workflow_id] = []

        self._telemetry[workflow_id].append({
            "duration_ms": max(0.0, float(duration_ms)),
            "is_success": bool(is_success),
            "error_message": error_message,
            "timestamp": datetime.now(timezone.utc),
        })

    def evaluate_health(
        self,
        workflow_id: UUID,
        workflow: Optional[Workflow] = None,
    ) -> WorkflowHealthReport:
        """Compute metrics, evaluate threshold breaches, and assemble health report."""
        records = self._telemetry.get(workflow_id, [])
        total = len(records)
        alerts: List[MonitoringAlert] = []
        health_checks: List[HealthCheckResult] = []

        if total == 0:
            return WorkflowHealthReport(
                workflow_id=workflow_id,
                overall_status=HealthStatus.UNKNOWN,
                total_executions=0,
                success_rate=1.0,
                failure_rate=0.0,
                average_duration_ms=0.0,
                p95_duration_ms=0.0,
                active_alerts=[],
                health_checks=[
                    HealthCheckResult(
                        component="Telemetry Ingestion",
                        status=HealthStatus.UNKNOWN,
                        message="No execution telemetry recorded yet for this workflow.",
                    )
                ],
            )

        successes = sum(1 for r in records if r["is_success"])
        failures = total - successes
        success_rate = successes / total
        failure_rate = failures / total

        durations = sorted(r["duration_ms"] for r in records)
        avg_duration = sum(durations) / total

        # Calculate P95 duration
        p95_idx = min(total - 1, math.floor(total * 0.95))
        p95_duration = durations[p95_idx]

        # 1. Failure rate alerting
        if failure_rate >= self.failure_rate_crit_threshold:
            alerts.append(
                MonitoringAlert(
                    workflow_id=workflow_id,
                    severity=AlertSeverity.CRITICAL,
                    title="Critical Failure Rate",
                    message=f"Workflow failure rate ({failure_rate:.1%}) exceeds critical threshold ({self.failure_rate_crit_threshold:.1%}).",
                    trigger_metric="failure_rate",
                    threshold=self.failure_rate_crit_threshold,
                    actual_value=failure_rate,
                )
            )
            health_checks.append(
                HealthCheckResult(
                    component="Reliability SLA",
                    status=HealthStatus.UNHEALTHY,
                    message=f"Failure rate is {failure_rate:.1%}",
                )
            )
        elif failure_rate >= self.failure_rate_warn_threshold:
            alerts.append(
                MonitoringAlert(
                    workflow_id=workflow_id,
                    severity=AlertSeverity.WARNING,
                    title="Elevated Failure Rate",
                    message=f"Workflow failure rate ({failure_rate:.1%}) exceeds warning threshold ({self.failure_rate_warn_threshold:.1%}).",
                    trigger_metric="failure_rate",
                    threshold=self.failure_rate_warn_threshold,
                    actual_value=failure_rate,
                )
            )
            health_checks.append(
                HealthCheckResult(
                    component="Reliability SLA",
                    status=HealthStatus.DEGRADED,
                    message=f"Failure rate is {failure_rate:.1%}",
                )
            )
        else:
            health_checks.append(
                HealthCheckResult(
                    component="Reliability SLA",
                    status=HealthStatus.HEALTHY,
                    message=f"Failure rate is {failure_rate:.1%}",
                )
            )

        # 2. Latency alerting
        if p95_duration >= self.p95_latency_threshold_ms:
            alerts.append(
                MonitoringAlert(
                    workflow_id=workflow_id,
                    severity=AlertSeverity.WARNING,
                    title="Elevated Latency",
                    message=f"P95 latency ({p95_duration:.0f}ms) exceeds SLA threshold ({self.p95_latency_threshold_ms:.0f}ms).",
                    trigger_metric="p95_duration_ms",
                    threshold=self.p95_latency_threshold_ms,
                    actual_value=p95_duration,
                )
            )
            health_checks.append(
                HealthCheckResult(
                    component="Performance SLA",
                    status=HealthStatus.DEGRADED,
                    message=f"P95 latency {p95_duration:.0f}ms exceeds threshold",
                    latency_ms=p95_duration,
                )
            )
        else:
            health_checks.append(
                HealthCheckResult(
                    component="Performance SLA",
                    status=HealthStatus.HEALTHY,
                    message=f"P95 latency {p95_duration:.0f}ms within bounds",
                    latency_ms=p95_duration,
                )
            )

        # 3. Workflow Container Health Check
        if workflow:
            if workflow.status == WorkflowStatus.ACTIVE:
                health_checks.append(
                    HealthCheckResult(
                        component="Workflow Container",
                        status=HealthStatus.HEALTHY,
                        message=f"Workflow is ACTIVE in {workflow.environment}",
                    )
                )
            elif workflow.status == WorkflowStatus.INACTIVE:
                health_checks.append(
                    HealthCheckResult(
                        component="Workflow Container",
                        status=HealthStatus.DEGRADED,
                        message="Workflow is currently INACTIVE",
                    )
                )
            else:
                health_checks.append(
                    HealthCheckResult(
                        component="Workflow Container",
                        status=HealthStatus.UNHEALTHY,
                        message=f"Workflow container is {workflow.status.value}",
                    )
                )

        # Determine overall status
        if any(a.severity == AlertSeverity.CRITICAL for a in alerts) or any(h.status == HealthStatus.UNHEALTHY for h in health_checks):
            overall_status = HealthStatus.UNHEALTHY
        elif any(a.severity == AlertSeverity.WARNING for a in alerts) or any(h.status == HealthStatus.DEGRADED for h in health_checks):
            overall_status = HealthStatus.DEGRADED
        else:
            overall_status = HealthStatus.HEALTHY

        return WorkflowHealthReport(
            workflow_id=workflow_id,
            overall_status=overall_status,
            total_executions=total,
            success_rate=success_rate,
            failure_rate=failure_rate,
            average_duration_ms=avg_duration,
            p95_duration_ms=p95_duration,
            active_alerts=alerts,
            health_checks=health_checks,
        )
