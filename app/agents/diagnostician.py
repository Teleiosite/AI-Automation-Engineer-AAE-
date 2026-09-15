"""Diagnostician Agent Component (Phase 14).

Agent interface for transforming execution and test failures into
structured root-cause diagnoses.
"""

from typing import Any, Dict, Optional
from uuid import UUID

from app.domain.models.specification import Specification
from app.domain.services.diagnosis_engine import (
    DiagnosisEngine,
    StructuredDiagnosis,
)
from app.domain.services.workflow_test_engine import TestCaseResult


class Diagnostician:
    """Agent component providing automated failure diagnosis."""

    def __init__(self, diagnosis_engine: Optional[DiagnosisEngine] = None) -> None:
        self.engine = diagnosis_engine or DiagnosisEngine()

    def diagnose_execution(
        self,
        execution_data: Dict[str, Any],
        workflow_id: Optional[UUID] = None,
        workflow_version_number: int = 1,
        specification: Optional[Specification] = None,
    ) -> StructuredDiagnosis:
        """Diagnose a runtime execution failure."""
        return self.engine.diagnose_execution(
            execution_data=execution_data,
            workflow_id=workflow_id,
            workflow_version_number=workflow_version_number,
            specification=specification,
        )

    def diagnose_test(
        self,
        test_result: TestCaseResult,
        workflow_id: UUID,
        workflow_version_number: int = 1,
        specification: Optional[Specification] = None,
    ) -> StructuredDiagnosis:
        """Diagnose a failed test case result."""
        return self.engine.diagnose_test_failure(
            test_result=test_result,
            workflow_id=workflow_id,
            workflow_version_number=workflow_version_number,
            specification=specification,
        )
