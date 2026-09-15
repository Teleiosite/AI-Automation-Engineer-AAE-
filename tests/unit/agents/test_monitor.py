"""Unit tests for WorkflowMonitor and MonitorAgent component (Phase 18)."""

import ast
from pathlib import Path
from uuid import uuid4
import pytest

from app.agents.diagnostician import Diagnostician
from app.agents.monitor import MonitorAgent
from app.domain.enums import WorkflowStatus
from app.domain.models.workflow import Workflow
from app.domain.services.workflow_monitor import (
    AlertSeverity,
    HealthStatus,
    MonitoringAlert,
    WorkflowHealthReport,
    WorkflowMonitor,
)


def test_monitor_domain_isolation():
    """Verify workflow_monitor.py has zero framework imports."""
    monitor_path = Path("app/domain/services/workflow_monitor.py")
    assert monitor_path.exists()

    tree = ast.parse(monitor_path.read_text(encoding="utf-8"))
    forbidden = {"fastapi", "sqlalchemy", "pydantic", "httpx", "n8n"}

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for name in node.names:
                root_pkg = name.name.split(".")[0]
                assert root_pkg not in forbidden, f"Forbidden import: {name.name}"
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                root_pkg = node.module.split(".")[0]
                assert root_pkg not in forbidden, f"Forbidden from-import: {node.module}"


def test_workflow_monitor_empty_telemetry():
    monitor = WorkflowMonitor()
    wf_id = uuid4()
    report = monitor.evaluate_health(wf_id)

    assert report.workflow_id == wf_id
    assert report.overall_status == HealthStatus.UNKNOWN
    assert report.total_executions == 0
    assert report.failure_rate == 0.0
    assert len(report.active_alerts) == 0


def test_workflow_monitor_healthy_executions():
    monitor = WorkflowMonitor()
    wf_id = uuid4()

    # 10 successful executions with low latency
    for _ in range(10):
        monitor.record_execution(wf_id, duration_ms=120.0, is_success=True)

    report = monitor.evaluate_health(wf_id)

    assert report.overall_status == HealthStatus.HEALTHY
    assert report.total_executions == 10
    assert report.success_rate == 1.0
    assert report.failure_rate == 0.0
    assert report.average_duration_ms == 120.0
    assert len(report.active_alerts) == 0


def test_workflow_monitor_warning_failure_rate():
    monitor = WorkflowMonitor(failure_rate_warn_threshold=0.10, failure_rate_crit_threshold=0.25)
    wf_id = uuid4()

    # 8 success, 2 failure -> 20% failure rate (between 10% and 25%)
    for _ in range(8):
        monitor.record_execution(wf_id, duration_ms=100.0, is_success=True)
    for _ in range(2):
        monitor.record_execution(wf_id, duration_ms=100.0, is_success=False, error_message="Timeout")

    report = monitor.evaluate_health(wf_id)

    assert report.overall_status == HealthStatus.DEGRADED
    assert report.failure_rate == 0.20
    assert len(report.active_alerts) == 1
    alert = report.active_alerts[0]
    assert alert.severity == AlertSeverity.WARNING
    assert alert.trigger_metric == "failure_rate"
    assert alert.threshold == 0.10


def test_workflow_monitor_critical_failure_rate():
    monitor = WorkflowMonitor(failure_rate_crit_threshold=0.25)
    wf_id = uuid4()

    # 6 success, 4 failures -> 40% failure rate (>= 25%)
    for _ in range(6):
        monitor.record_execution(wf_id, duration_ms=100.0, is_success=True)
    for _ in range(4):
        monitor.record_execution(wf_id, duration_ms=100.0, is_success=False, error_message="Fatal crash")

    report = monitor.evaluate_health(wf_id)

    assert report.overall_status == HealthStatus.UNHEALTHY
    assert report.failure_rate == 0.40
    assert len(report.active_alerts) == 1
    alert = report.active_alerts[0]
    assert alert.severity == AlertSeverity.CRITICAL


def test_workflow_monitor_p95_latency_alert():
    monitor = WorkflowMonitor(p95_latency_threshold_ms=1000.0)
    wf_id = uuid4()

    # 19 runs at 100ms, 1 run at 2500ms -> p95 >= 1000ms
    for _ in range(19):
        monitor.record_execution(wf_id, duration_ms=100.0, is_success=True)
    monitor.record_execution(wf_id, duration_ms=2500.0, is_success=True)

    report = monitor.evaluate_health(wf_id)

    assert report.overall_status == HealthStatus.DEGRADED
    assert any(a.trigger_metric == "p95_duration_ms" for a in report.active_alerts)
    latency_alert = next(a for a in report.active_alerts if a.trigger_metric == "p95_duration_ms")
    assert latency_alert.severity == AlertSeverity.WARNING
    assert latency_alert.actual_value >= 1000.0


def test_workflow_container_health_check():
    monitor = WorkflowMonitor()
    wf = Workflow(project_id=uuid4(), name="Order Processor")
    wf.status = WorkflowStatus.ACTIVE

    # Record 5 successful runs
    for _ in range(5):
        monitor.record_execution(wf.id, duration_ms=50.0, is_success=True)

    report = monitor.evaluate_health(wf.id, workflow=wf)
    assert report.overall_status == HealthStatus.HEALTHY
    container_check = next(h for h in report.health_checks if h.component == "Workflow Container")
    assert container_check.status == HealthStatus.HEALTHY


def test_monitor_agent_check_and_escalate():
    monitor = WorkflowMonitor(failure_rate_crit_threshold=0.25)
    diagnostician = Diagnostician()
    agent = MonitorAgent(monitor_service=monitor, diagnostician=diagnostician)

    wf = Workflow(project_id=uuid4(), name="Payment Webhook Handler")
    wf.status = WorkflowStatus.ACTIVE

    # 1 success, 4 failures -> 80% failure rate -> CRITICAL alert
    agent.record_run(wf.id, duration_ms=50.0, is_success=True)
    for _ in range(4):
        agent.record_run(
            wf.id,
            duration_ms=50.0,
            is_success=False,
            error_message="HTTP 401 Unauthorized: Invalid API Token",
        )

    report, diagnosis = agent.check_and_escalate(wf)

    assert report.overall_status == HealthStatus.UNHEALTHY
    assert diagnosis is not None
    assert diagnosis.workflow_id == wf.id
    assert "Invalid API Token" in diagnosis.error_message or "critical" in diagnosis.error_message.lower()
