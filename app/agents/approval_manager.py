"""Approval Manager Agent Component (Phase 8).

Coordinates specification review submission and human governance approval tokens.
"""

from typing import Optional
from app.domain.models.approval import Approval
from app.domain.models.specification import Specification
from app.domain.services.specification_service import SpecificationService


class ApprovalManager:
    """Agent component responsible for facilitating the human approval workflow."""

    def __init__(self, specification_service: SpecificationService) -> None:
        self.specification_service = specification_service

    def request_approval(
        self,
        specification: Specification,
        actor: str = "agent",
        correlation_id: Optional[str] = None,
    ) -> None:
        """Submit an implementation specification for formal human review."""
        self.specification_service.submit_for_review(
            specification=specification,
            actor=actor,
            correlation_id=correlation_id,
        )

    def record_decision(
        self,
        specification: Specification,
        version_number: int,
        approver: str,
        decision: str,
        comments: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> Optional[Approval]:
        """Record human governance decision ('APPROVED', 'REJECTED', 'CHANGES_REQUESTED')."""
        normalized_decision = decision.strip().upper()
        if normalized_decision == "APPROVED":
            return self.specification_service.approve_specification(
                specification=specification,
                version_number=version_number,
                approver=approver,
                comments=comments,
                correlation_id=correlation_id,
            )
        elif normalized_decision == "REJECTED":
            self.specification_service.reject_specification(
                specification=specification,
                rejecter=approver,
                reason=comments or "Rejected by human reviewer",
                correlation_id=correlation_id,
            )
            return None
        elif normalized_decision in ("CHANGES_REQUESTED", "CLARIFICATION_REQUIRED"):
            self.specification_service.request_changes(
                specification=specification,
                actor=approver,
                feedback=comments or "Changes requested by reviewer",
                correlation_id=correlation_id,
            )
            return None
        else:
            raise ValueError(f"Unknown approval decision: {decision}")
