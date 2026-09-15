"""Failure Diagnosis Engine Service (§15 AAE_AGENT_SPECIFICATION, §35 CODEX_IMPLEMENTATION_PLAN).

Transforms failed execution logs and test outcomes into structured, deterministic
root-cause diagnoses without guessing or claiming certainty when evidence is insufficient.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import re
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID, uuid4

from app.domain.enums import (
    ConfidenceLevel,
    FailureCategory,
    FailureSeverity,
    RiskLevel,
)
from app.domain.errors import DomainValidationError
from app.domain.models.diagnostic import DiagnosticFinding, FailureRecord
from app.domain.models.specification import Specification
from app.domain.services.workflow_test_engine import TestCaseResult


@dataclass(frozen=True)
class StructuredDiagnosis:
    """Standardized root-cause diagnosis for an execution or test failure."""
    execution_id: UUID
    workflow_id: UUID
    workflow_version_number: int
    failure_node: str
    failure_type: FailureCategory
    severity: FailureSeverity
    error_message: str
    execution_path: List[str]
    last_successful_node: Optional[str]
    likely_cause: str
    confidence: ConfidenceLevel
    confidence_score: float
    recommended_action: str
    affected_requirement: Optional[str] = None
    suggested_fix_patch: Optional[Dict[str, Any]] = None
    risk: RiskLevel = RiskLevel.LOW
    id: UUID = field(default_factory=uuid4)
    diagnosed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if not (0.0 <= self.confidence_score <= 1.0):
            raise DomainValidationError("Confidence score must be between 0.0 and 1.0")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "execution_id": str(self.execution_id),
            "workflow_id": str(self.workflow_id),
            "workflow_version_number": self.workflow_version_number,
            "failure_node": self.failure_node,
            "failure_type": self.failure_type.value,
            "severity": self.severity.value,
            "error_message": self.error_message,
            "execution_path": self.execution_path,
            "last_successful_node": self.last_successful_node,
            "likely_cause": self.likely_cause,
            "confidence": self.confidence.value,
            "confidence_score": self.confidence_score,
            "recommended_action": self.recommended_action,
            "affected_requirement": self.affected_requirement,
            "suggested_fix_patch": self.suggested_fix_patch,
            "risk": self.risk.value,
            "diagnosed_at": self.diagnosed_at.isoformat(),
        }


class DiagnosisEngine:
    """Engine parsing error signatures and computing structured root-cause diagnoses."""

    ERROR_SIGNATURES: List[Tuple[re.Pattern, FailureCategory, FailureSeverity, ConfidenceLevel, float, str, str]] = [
        # Authentication & Authorization
        (
            re.compile(r"\b(401|unauthorized|invalid credentials|expired token|auth failed)\b", re.IGNORECASE),
            FailureCategory.AUTHENTICATION_ERROR,
            FailureSeverity.HIGH,
            ConfidenceLevel.EXPLICIT,
            0.95,
            "Authentication failed: invalid or expired provider credentials or access token.",
            "Verify credential binding, refresh OAuth/API token, or update credential reference in node settings.",
        ),
        (
            re.compile(r"\b(403|forbidden|permission denied|insufficient permissions)\b", re.IGNORECASE),
            FailureCategory.PERMISSION_ERROR,
            FailureSeverity.HIGH,
            ConfidenceLevel.EXPLICIT,
            0.95,
            "Permission denied: actor lacks required role or API scope.",
            "Elevate API token permissions or grant necessary access scopes to target resource.",
        ),
        # Timeouts & Networking
        (
            re.compile(r"\b(timeout|timed out|504|etimedout|econnrefused|connection refused|network error)\b", re.IGNORECASE),
            FailureCategory.TIMEOUT,
            FailureSeverity.MEDIUM,
            ConfidenceLevel.EXPLICIT,
            0.95,
            "Network timeout or downstream connectivity failure.",
            "Configure node retryOnFail policy with maxTries=3 and verify downstream service reachability.",
        ),
        # Rate Limiting
        (
            re.compile(r"\b(429|too many requests|rate limit|quota exceeded)\b", re.IGNORECASE),
            FailureCategory.RATE_LIMIT,
            FailureSeverity.MEDIUM,
            ConfidenceLevel.EXPLICIT,
            0.95,
            "Upstream service rate limit or quota exceeded.",
            "Implement exponential backoff or add rate-limiting interval between executions.",
        ),
        # Data & Database Errors
        (
            re.compile(r"\b(duplicate key|unique constraint|not null|foreign key|constraint violation)\b", re.IGNORECASE),
            FailureCategory.DATA_ERROR,
            FailureSeverity.MEDIUM,
            ConfidenceLevel.INFERRED,
            0.85,
            "Database constraint violation or schema mismatch in operation payload.",
            "Ensure input payload satisfies uniqueness constraints and nullability requirements.",
        ),
        # Configuration & Expression Syntax
        (
            re.compile(r"\b(syntax\s*error|unexpected token|unbalanced|invalid expression|cannot read property|is undefined|json parse)\b", re.IGNORECASE),
            FailureCategory.CONFIGURATION_ERROR,
            FailureSeverity.HIGH,
            ConfidenceLevel.INFERRED,
            0.85,
            "Node configuration contains malformed syntax, invalid expression, or missing parameter.",
            "Correct parameter expression syntax (e.g. {{ $json.field }}) and verify upstream output availability.",
        ),
        # Semantic & Business Logic
        (
            re.compile(r"\b(semantic expectation|missing expected output|semantic assertion|unsatisfied)\b", re.IGNORECASE),
            FailureCategory.LOGIC_ERROR,
            FailureSeverity.HIGH,
            ConfidenceLevel.EXPLICIT,
            0.90,
            "Workflow execution succeeded technically but failed business semantic criteria.",
            "Adjust mapping transformation to produce expected output attributes required by specification.",
        ),
    ]

    def diagnose_execution(
        self,
        execution_data: Dict[str, Any],
        workflow_id: Optional[UUID] = None,
        workflow_version_number: int = 1,
        specification: Optional[Specification] = None,
    ) -> StructuredDiagnosis:
        """Analyze execution failure data and produce deterministic StructuredDiagnosis."""
        exec_id_str = str(execution_data.get("id", uuid4()))
        try:
            exec_id = UUID(exec_id_str)
        except ValueError:
            exec_id = uuid4()

        wf_id = workflow_id or uuid4()
        error_msg = str(execution_data.get("error_message") or execution_data.get("error") or "Unknown execution error")
        failed_node = str(execution_data.get("failed_node") or execution_data.get("node_name") or "Unknown Node")

        # Reconstruct execution path
        raw_path = execution_data.get("execution_path") or execution_data.get("visited_nodes") or []
        execution_path = [str(n) for n in raw_path] if isinstance(raw_path, list) else []
        if failed_node and (not execution_path or execution_path[-1] != failed_node):
            execution_path.append(failed_node)

        # Identify last successful node
        last_successful_node = None
        if len(execution_path) >= 2:
            last_successful_node = execution_path[-2]

        # Signature matching
        category, severity, confidence, conf_score, cause, action = self._classify_error(error_msg)

        # Identify affected requirement
        affected_req = None
        if specification:
            cur_ver = specification.get_current_version()
            if cur_ver:
                content = cur_ver.structured_content
                criteria = content.get("success_criteria", [])
                if criteria:
                    affected_req = f"Violates success criteria: {criteria[0]}"

        # Risk classification
        risk = RiskLevel.LOW
        if severity in (FailureSeverity.HIGH, FailureSeverity.CRITICAL):
            risk = RiskLevel.MEDIUM

        return StructuredDiagnosis(
            execution_id=exec_id,
            workflow_id=wf_id,
            workflow_version_number=workflow_version_number,
            failure_node=failed_node,
            failure_type=category,
            severity=severity,
            error_message=error_msg,
            execution_path=execution_path,
            last_successful_node=last_successful_node,
            likely_cause=cause,
            confidence=confidence,
            confidence_score=conf_score,
            recommended_action=action,
            affected_requirement=affected_req,
            risk=risk,
        )

    def diagnose_test_failure(
        self,
        test_result: TestCaseResult,
        workflow_id: UUID,
        workflow_version_number: int = 1,
        specification: Optional[Specification] = None,
    ) -> StructuredDiagnosis:
        """Produce structured diagnosis directly from a failed TestCaseResult."""
        error_msg = test_result.error_message or "Test scenario assertions failed"

        # Determine failed assertion details
        failed_assertion = None
        for a in test_result.assertions:
            if not a.passed:
                failed_assertion = a
                break

        failed_node = "Unknown Node"
        if failed_assertion and "node." in failed_assertion.target:
            failed_node = failed_assertion.target.replace("node.", "")
        elif failed_assertion:
            failed_node = failed_assertion.target

        raw_msg = f"{error_msg} | {failed_assertion.message if failed_assertion else ''}"
        category, severity, confidence, conf_score, cause, action = self._classify_error(raw_msg)

        return StructuredDiagnosis(
            execution_id=test_result.test_id,
            workflow_id=workflow_id,
            workflow_version_number=workflow_version_number,
            failure_node=failed_node,
            failure_type=category,
            severity=severity,
            error_message=raw_msg,
            execution_path=[failed_node],
            last_successful_node=None,
            likely_cause=cause,
            confidence=confidence,
            confidence_score=conf_score,
            recommended_action=action,
            affected_requirement=f"Scenario: {test_result.scenario_name}",
            risk=RiskLevel.LOW,
        )

    def _classify_error(
        self,
        error_message: str,
    ) -> Tuple[FailureCategory, FailureSeverity, ConfidenceLevel, float, str, str]:
        """Match error string against calibrated signatures or return restrained fallback."""
        for pattern, cat, sev, conf, score, cause, action in self.ERROR_SIGNATURES:
            if pattern.search(error_message):
                return cat, sev, conf, score, cause, action

        # Fallback for ambiguous or unclassified errors (strictly restrained confidence)
        return (
            FailureCategory.UNKNOWN,
            FailureSeverity.MEDIUM,
            ConfidenceLevel.UNKNOWN,
            0.40,  # Restrained: never claim certainty without evidence
            f"Unclassified error signature: '{error_message[:100]}'.",
            "Examine raw stack trace and node execution parameters to identify failure mechanism.",
        )
