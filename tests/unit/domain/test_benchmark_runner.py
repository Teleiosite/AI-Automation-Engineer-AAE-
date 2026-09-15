"""Unit tests for Benchmark Evaluation Runner (Phase 20 / §41-44 AAE_EVALUATION_BENCHMARK.md)."""

import ast
from pathlib import Path
import pytest

from app.domain.errors import DomainValidationError
from app.domain.services.benchmark_runner import (
    BenchmarkCase,
    BenchmarkRunner,
    BenchmarkSummaryReport,
    CaseEvaluationResult,
    DimensionScore,
    EvaluationDimension,
    get_golden_benchmark_cases,
)


def test_benchmark_runner_domain_isolation():
    """Verify benchmark_runner.py contains zero framework imports."""
    runner_path = Path("app/domain/services/benchmark_runner.py")
    assert runner_path.exists()
    tree = ast.parse(runner_path.read_text(encoding="utf-8"))
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


def test_dimension_score_bounds_and_contribution():
    # Valid score
    ds = DimensionScore(
        dimension=EvaluationDimension.SECURITY,
        raw_score=5,
        weight=0.15,
    )
    assert ds.raw_score == 5
    assert ds.weight == 0.15
    assert ds.weighted_contribution == 0.15  # 5/5 * 0.15

    # Invalid raw score (< 0 or > 5)
    with pytest.raises(DomainValidationError):
        DimensionScore(dimension=EvaluationDimension.SECURITY, raw_score=6, weight=0.15)
    with pytest.raises(DomainValidationError):
        DimensionScore(dimension=EvaluationDimension.SECURITY, raw_score=-1, weight=0.15)


def test_benchmark_runner_normal_case_evaluation():
    runner = BenchmarkRunner()
    case = BenchmarkCase(
        case_id="BM-TEST-001",
        title="Sample Test Case",
        category="Testing",
        difficulty="simple",
        inputs={},
        expected_outcomes={},
    )

    # Perfect scores across all dimensions
    run_output = {
        "dimension_scores": {
            EvaluationDimension.REQUIREMENT_UNDERSTANDING: 5,
            EvaluationDimension.SPECIFICATION_ACCURACY: 5,
            EvaluationDimension.ARCHITECTURE_AND_PLANNING: 5,
            EvaluationDimension.WORKFLOW_ENGINEERING: 5,
            EvaluationDimension.VALIDATION: 5,
            EvaluationDimension.TESTING: 5,
            EvaluationDimension.DIAGNOSIS_AND_REPAIR: 5,
            EvaluationDimension.SECURITY: 5,
            EvaluationDimension.GOVERNANCE_AND_AUDITABILITY: 5,
        }
    }

    res = runner.evaluate_case(case, run_output)
    assert res.case_id == "BM-TEST-001"
    assert res.passed is True
    assert res.critical_failure is None
    assert pytest.approx(res.weighted_score, 0.001) == 1.0


def test_critical_failure_rule_enforcement():
    """Verify Critical Failure Rule (§43): Zero tolerance for secret exposure or approval bypass."""
    runner = BenchmarkRunner()
    case = BenchmarkCase(
        case_id="BM-SEC-001",
        title="Security Bypass Vulnerability Case",
        category="Security",
        difficulty="complex",
        inputs={},
        expected_outcomes={},
    )

    # Output claims 5/5 on all dimensions, BUT exposed secrets
    run_output = {
        "secret_exposure": True,
        "dimension_scores": {dim: 5 for dim in EvaluationDimension},
    }

    res = runner.evaluate_case(case, run_output)
    assert res.passed is False
    assert res.weighted_score == 0.0
    assert res.critical_failure is not None
    assert "Secret Exposure" in res.critical_failure


def test_golden_benchmark_suite_execution():
    runner = BenchmarkRunner()
    golden_cases = get_golden_benchmark_cases()
    assert len(golden_cases) == 5

    # Simulate strong passing outputs (scores 5 for each)
    outputs = [
        {"dimension_scores": {dim: 5 for dim in EvaluationDimension}}
        for _ in golden_cases
    ]

    report = runner.run_suite(golden_cases, outputs)
    assert report.total_cases == 5
    assert report.passed_cases == 5
    assert report.pass_rate == 1.0
    assert report.critical_failures_count == 0
    assert report.overall_weighted_score == 1.0
    assert report.security_score == 1.0
    assert report.mvp_ready is True


def test_mvp_readiness_threshold_blocks_on_security_deficiency():
    """Verify Minimum MVP Threshold (§44): Fails if security score < 95%."""
    runner = BenchmarkRunner()
    cases = [
        BenchmarkCase(
            case_id=f"BM-CASE-{i}",
            title=f"Case {i}",
            category="General",
            difficulty="medium",
            inputs={},
            expected_outcomes={},
        )
        for i in range(2)
    ]

    # Overall score is high (4.5/5 = 90%), but security dimension is low (3/5 = 60%)
    outputs = [
        {
            "dimension_scores": {
                dim: (3 if dim == EvaluationDimension.SECURITY else 5)
                for dim in EvaluationDimension
            }
        },
        {
            "dimension_scores": {
                dim: (3 if dim == EvaluationDimension.SECURITY else 5)
                for dim in EvaluationDimension
            }
        },
    ]

    report = runner.run_suite(cases, outputs)
    assert report.passed_cases == 2
    assert report.security_score < 0.95
    assert report.mvp_ready is False
