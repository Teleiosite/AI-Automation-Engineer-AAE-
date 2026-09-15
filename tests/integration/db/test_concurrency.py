"""Concurrency, race-condition, and transaction rollback tests."""

import concurrent.futures
from uuid import uuid4
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.db.base import Base
from app.db.repositories.approval_repo import ApprovalRepository
from app.db.repositories.project_repo import ProjectRepository
from app.db.repositories.requirement_repo import RequirementRepository
from app.db.repositories.specification_repo import SpecificationRepository
from app.db.repositories.workflow_repo import WorkflowRepository
from app.db.unit_of_work import UnitOfWork
from app.domain.enums import AgentState, ApprovalStatus, ApprovalTargetType
from app.domain.errors import StaleApprovalError
from app.domain.models.approval import Approval
from app.domain.models.project import Project
from app.domain.models.requirement import Requirement
from app.domain.models.specification import Specification
from app.domain.models.workflow import Workflow


@pytest.fixture
def thread_safe_engine(tmp_path):
    db_file = tmp_path / "concurrency_test.db"
    engine = create_engine(
        f"sqlite:///{db_file}",
        connect_args={"timeout": 30},
    )
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


def test_concurrent_workflow_version_allocation(thread_safe_engine):
    """
    Verify that concurrent version creation attempts for the same workflow
    never result in duplicate committed version numbers.
    """
    session_factory = sessionmaker(bind=thread_safe_engine)

    # Setup parent workflow
    with session_factory() as s:
        p_repo = ProjectRepository(s)
        w_repo = WorkflowRepository(s)
        proj = p_repo.save(Project(name="ConcurrentProj"))
        wf = w_repo.save(Workflow(project_id=proj.id, name="ConcurrentWorkflow"))
        wf_id = wf.id
        s.commit()

    spec_ver_id = uuid4()

    def create_version_worker(worker_idx):
        with session_factory() as worker_session:
            worker_w_repo = WorkflowRepository(worker_session)
            try:
                ver = worker_w_repo.create_version_atomic(
                    workflow_id=wf_id,
                    specification_version_id=spec_ver_id,
                    definition={"worker": worker_idx},
                )
                worker_session.commit()
                return ver.version_number
            except Exception as e:
                worker_session.rollback()
                return f"ERROR: {type(e).__name__}"

    # Run 5 concurrent version allocations
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(create_version_worker, i) for i in range(5)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    # Check committed versions in the database
    with session_factory() as s:
        from app.db.models.workflow import WorkflowVersionModel
        from sqlalchemy import select
        versions = s.scalars(
            select(WorkflowVersionModel).where(WorkflowVersionModel.workflow_id == wf_id)
        ).all()
        committed_versions = [v.version_number for v in versions]

    # Invariant: strictly no duplicate version numbers committed in the database
    assert len(committed_versions) == len(set(committed_versions)), f"Duplicate committed versions found: {committed_versions}"
    assert len(committed_versions) >= 1


def test_concurrent_specification_version_allocation(thread_safe_engine):
    """
    Verify that concurrent version creation attempts for the same specification
    never result in duplicate committed version numbers.
    """
    session_factory = sessionmaker(bind=thread_safe_engine)

    # Setup parent project, requirement, and specification
    with session_factory() as s:
        p_repo = ProjectRepository(s)
        r_repo = RequirementRepository(s)
        sp_repo = SpecificationRepository(s)
        proj = p_repo.save(Project(name="ConcurrentSpecProj"))
        req = r_repo.save(Requirement(project_id=proj.id, original_request="Raw spec request"))
        spec = sp_repo.save(Specification(project_id=proj.id, requirement_id=req.id))
        spec_id = spec.id
        s.commit()

    def create_spec_version_worker(worker_idx):
        with session_factory() as worker_session:
            worker_sp_repo = SpecificationRepository(worker_session)
            try:
                ver = worker_sp_repo.create_version_atomic(
                    specification_id=spec_id,
                    structured_content={"worker": worker_idx, "nodes": []},
                )
                worker_session.commit()
                return ver.version_number
            except Exception as e:
                worker_session.rollback()
                return f"ERROR: {type(e).__name__}"

    # Run 5 concurrent version allocations
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(create_spec_version_worker, i) for i in range(5)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    # Check committed versions in the database
    with session_factory() as s:
        from app.db.models.specification import SpecificationVersionModel
        from sqlalchemy import select
        versions = s.scalars(
            select(SpecificationVersionModel).where(SpecificationVersionModel.specification_id == spec_id)
        ).all()
        committed_versions = [v.version_number for v in versions]

    # Invariant: strictly no duplicate version numbers committed in the database
    assert len(committed_versions) == len(set(committed_versions)), f"Duplicate committed versions found: {committed_versions}"
    assert len(committed_versions) >= 1


def test_concurrent_approval_consumption_single_winner(thread_safe_engine):
    """
    Verify that when two concurrent transactions attempt to consume the same ACTIVE approval,
    exactly ONE succeeds and the other receives StaleApprovalError.
    """
    session_factory = sessionmaker(bind=thread_safe_engine)

    # Setup approval
    with session_factory() as s:
        a_repo = ApprovalRepository(s)
        approval = Approval(
            target_type=ApprovalTargetType.WORKFLOW_VERSION,
            target_id=uuid4(),
            target_version=1,
            actor="security_lead",
            action="deploy",
        )
        approval.approve()
        saved = a_repo.save(approval)
        approval_id = saved.id
        s.commit()

    action_1 = uuid4()
    action_2 = uuid4()

    outcomes = []

    def consume_worker(action_id):
        with session_factory() as worker_session:
            worker_a_repo = ApprovalRepository(worker_session)
            try:
                consumed = worker_a_repo.consume_atomic(approval_id, action_id)
                worker_session.commit()
                outcomes.append(("SUCCESS", action_id))
            except StaleApprovalError as e:
                worker_session.rollback()
                outcomes.append(("STALE_ERROR", str(e)))
            except Exception as e:
                worker_session.rollback()
                outcomes.append(("OTHER_ERROR", str(e)))

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(consume_worker, action_1)
        f2 = executor.submit(consume_worker, action_2)
        concurrent.futures.wait([f1, f2])

    success_count = sum(1 for status, _ in outcomes if status == "SUCCESS")
    stale_count = sum(1 for status, _ in outcomes if status == "STALE_ERROR")

    assert success_count == 1, f"Expected exactly 1 success, got outcomes: {outcomes}"
    assert stale_count == 1, f"Expected exactly 1 StaleApprovalError, got outcomes: {outcomes}"


def test_atomic_deployment_authorization_rollback_preserves_approval(thread_safe_engine):
    """
    Verify that if deployment record creation fails during the authorization transaction,
    the transaction is rolled back, the approval remains ACTIVE, and no deployment is committed.
    """
    session_factory = sessionmaker(bind=thread_safe_engine)

    with session_factory() as s:
        p_repo = ProjectRepository(s)
        w_repo = WorkflowRepository(s)
        a_repo = ApprovalRepository(s)

        proj = p_repo.save(Project(name="RollbackProj"))
        wf = w_repo.save(Workflow(project_id=proj.id, name="RollbackWorkflow"))
        v1 = w_repo.create_version_atomic(
            workflow_id=wf.id,
            specification_version_id=uuid4(),
            definition={"step": 1},
        )
        v1.validate()
        v1.mark_tested()
        v1.mark_approved()
        w_repo.save(wf)

        approval = Approval(
            target_type=ApprovalTargetType.WORKFLOW_VERSION,
            target_id=wf.id,
            target_version=v1.version_number,
            actor="lead_ops",
            environment="production",
        )
        approval.approve()
        saved_appr = a_repo.save(approval)
        wf_id = wf.id
        appr_id = saved_appr.id
        s.commit()

    uow = UnitOfWork(session_factory)

    # Attempt to deploy with AgentState.TESTING (invalid state, policy must reject and rollback)
    with pytest.raises(Exception):
        with uow:
            uow.authorize_and_create_deployment(
                workflow_id=wf_id,
                workflow_version_number=1,
                approval_id=appr_id,
                agent_state=AgentState.TESTING,  # INVALID state
                target_environment="production",
                deployed_by="agent",
            )
            uow.commit()

    # Verify that the approval in database is STILL ACTIVE
    with session_factory() as s:
        a_repo = ApprovalRepository(s)
        persisted_appr = a_repo.get(appr_id)
        assert persisted_appr is not None
        assert persisted_appr.status == ApprovalStatus.ACTIVE
        assert persisted_appr.consumed_at is None
        assert persisted_appr.consumed_by_action_id is None


def test_approval_version_mismatch_rejected(thread_safe_engine):
    """
    Verify that an approval issued for Version 1 is deterministically rejected
    when attempted on Version 2.
    """
    session_factory = sessionmaker(bind=thread_safe_engine)

    with session_factory() as s:
        p_repo = ProjectRepository(s)
        w_repo = WorkflowRepository(s)
        a_repo = ApprovalRepository(s)

        proj = p_repo.save(Project(name="MismatchProj"))
        wf = w_repo.save(Workflow(project_id=proj.id, name="MismatchWorkflow"))
        v1 = w_repo.create_version_atomic(
            workflow_id=wf.id,
            specification_version_id=uuid4(),
            definition={"step": 1},
        )
        v1.validate()
        v1.mark_tested()
        v1.mark_approved()

        v2 = w_repo.create_version_atomic(
            workflow_id=wf.id,
            specification_version_id=uuid4(),
            definition={"step": 2},
        )
        v2.validate()
        v2.mark_tested()
        v2.mark_approved()
        w_repo.save(wf)

        approval_v1 = Approval(
            target_type=ApprovalTargetType.WORKFLOW_VERSION,
            target_id=wf.id,
            target_version=1,  # Approved for version 1
            actor="lead_ops",
            environment="production",
        )
        approval_v1.approve()
        saved_appr = a_repo.save(approval_v1)
        wf_id = wf.id
        appr_id = saved_appr.id
        s.commit()

    uow = UnitOfWork(session_factory)
    with pytest.raises(StaleApprovalError):
        with uow:
            uow.authorize_and_create_deployment(
                workflow_id=wf_id,
                workflow_version_number=2,  # Attempting to deploy version 2 using v1 approval!
                approval_id=appr_id,
                agent_state=AgentState.APPROVED,
                target_environment="production",
                deployed_by="agent",
            )
            uow.commit()
