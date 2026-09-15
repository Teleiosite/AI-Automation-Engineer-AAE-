"""Unit tests for Approval entity and replay defense."""

from datetime import datetime, timedelta, timezone
import pytest
from uuid import uuid4
from app.domain.enums import ApprovalDecision, ApprovalStatus, ApprovalTargetType
from app.domain.errors import StaleApprovalError
from app.domain.models.approval import Approval


def test_approval_lifecycle_and_validation():
    wf_id = uuid4()
    approval = Approval(
        target_type=ApprovalTargetType.WORKFLOW_VERSION,
        target_id=wf_id,
        target_version=1,
        actor="lead_engineer",
        environment="production",
        action="deploy",
    )
    assert approval.decision == ApprovalDecision.PENDING
    assert approval.status == ApprovalStatus.PENDING

    # Not valid while PENDING
    assert not approval.is_valid_for(
        target_type=ApprovalTargetType.WORKFLOW_VERSION,
        target_id=wf_id,
        target_version=1,
        environment="production",
        action="deploy",
    )

    # Approve
    approval.approve(comments="Approved for release")
    assert approval.decision == ApprovalDecision.APPROVED
    assert approval.status == ApprovalStatus.ACTIVE

    # Matches exact target
    assert approval.is_valid_for(
        target_type=ApprovalTargetType.WORKFLOW_VERSION,
        target_id=wf_id,
        target_version=1,
        environment="production",
        action="deploy",
    )

    # Rejects version mismatch
    assert not approval.is_valid_for(
        target_type=ApprovalTargetType.WORKFLOW_VERSION,
        target_id=wf_id,
        target_version=2,  # Version 2 not authorized by Version 1 approval
        environment="production",
        action="deploy",
    )

    # Rejects environment mismatch
    assert not approval.is_valid_for(
        target_type=ApprovalTargetType.WORKFLOW_VERSION,
        target_id=wf_id,
        target_version=1,
        environment="staging",
        action="deploy",
    )


def test_approval_single_use_replay_defense():
    wf_id = uuid4()
    action_id = uuid4()
    approval = Approval(
        target_type=ApprovalTargetType.WORKFLOW_VERSION,
        target_id=wf_id,
        target_version=1,
        actor="lead_engineer",
    )
    approval.approve()

    # Consume once
    approval.consume(action_id=action_id)
    assert approval.status == ApprovalStatus.CONSUMED
    assert approval.consumed_by_action_id == action_id

    # Second consumption attempt must raise StaleApprovalError (prevents replay attack)
    second_action_id = uuid4()
    with pytest.raises(StaleApprovalError) as exc_info:
        approval.consume(action_id=second_action_id)
    assert "already consumed" in str(exc_info.value)


def test_expired_approval_cannot_be_consumed():
    approval = Approval(
        target_type=ApprovalTargetType.WORKFLOW_VERSION,
        target_id=uuid4(),
        target_version=1,
        actor="lead_engineer",
    )
    past_expiry = datetime.now(timezone.utc) - timedelta(hours=1)
    approval.approve(expires_at=past_expiry)

    assert not approval.is_valid_for(
        target_type=ApprovalTargetType.WORKFLOW_VERSION,
        target_id=approval.target_id,
        target_version=1,
    )

    with pytest.raises(StaleApprovalError) as exc_info:
        approval.consume(action_id=uuid4())
    assert "expired" in str(exc_info.value)
