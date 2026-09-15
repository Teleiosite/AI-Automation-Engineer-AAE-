"""Diagnostic and FailureRecord repository adapter."""

from typing import List, Optional
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db.mappers.diagnostic_mapper import (
    diagnostic_finding_to_domain,
    diagnostic_finding_to_model,
    failure_record_to_domain,
    failure_record_to_model,
)
from app.db.models.diagnostic import DiagnosticFindingModel, FailureRecordModel
from app.domain.models.diagnostic import DiagnosticFinding, FailureRecord


class DiagnosticRepository:
    """Repository managing FailureRecord and DiagnosticFinding persistence."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def save_failure(self, failure: FailureRecord) -> FailureRecord:
        """Persist a failure incident record."""
        stmt = select(FailureRecordModel).where(FailureRecordModel.id == failure.id)
        model = self._session.execute(stmt).scalar_one_or_none()
        if not model:
            model = failure_record_to_model(failure)
            self._session.add(model)
        self._session.flush()
        return failure_record_to_domain(model)

    def get_failure(self, failure_id: UUID) -> Optional[FailureRecord]:
        """Fetch failure record by UUID."""
        stmt = select(FailureRecordModel).where(FailureRecordModel.id == failure_id)
        model = self._session.execute(stmt).scalar_one_or_none()
        return failure_record_to_domain(model) if model else None

    def list_failures_for_execution(self, execution_id: UUID) -> List[FailureRecord]:
        """List failure records for an execution."""
        stmt = (
            select(FailureRecordModel)
            .where(FailureRecordModel.execution_id == execution_id)
            .order_by(FailureRecordModel.timestamp.desc())
        )
        models = self._session.execute(stmt).scalars().all()
        return [failure_record_to_domain(m) for m in models]

    def save_finding(self, finding: DiagnosticFinding) -> DiagnosticFinding:
        """Persist a root cause diagnostic finding."""
        stmt = select(DiagnosticFindingModel).where(DiagnosticFindingModel.id == finding.id)
        model = self._session.execute(stmt).scalar_one_or_none()
        if not model:
            model = diagnostic_finding_to_model(finding)
            self._session.add(model)
        self._session.flush()
        return diagnostic_finding_to_domain(model)

    def get_finding(self, finding_id: UUID) -> Optional[DiagnosticFinding]:
        """Fetch diagnostic finding by UUID."""
        stmt = select(DiagnosticFindingModel).where(DiagnosticFindingModel.id == finding_id)
        model = self._session.execute(stmt).scalar_one_or_none()
        return diagnostic_finding_to_domain(model) if model else None
