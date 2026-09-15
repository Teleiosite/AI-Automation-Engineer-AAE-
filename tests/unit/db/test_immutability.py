"""Unit tests verifying immutability enforcement across repository and domain layers."""

from uuid import uuid4
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.base import Base
from app.db.repositories.audit_repo import AuditRepository
from app.db.repositories.project_repo import ProjectRepository
from app.db.repositories.specification_repo import SpecificationRepository
from app.db.repositories.workflow_repo import WorkflowRepository
from app.domain.enums import WorkflowStatus, WorkflowVersionStatus
from app.domain.errors import ImmutableArtifactError
from app.domain.models.project import Project
from app.domain.models.specification import Specification
from app.domain.models.workflow import Workflow


@pytest.fixture
def memory_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    yield session
    session.close()


def test_approved_specification_version_immutability_in_repository(memory_db):
    spec_repo = SpecificationRepository(memory_db)
    proj_repo = ProjectRepository(memory_db)

    project = proj_repo.save(Project(name="TestProj"))
    spec = Specification(project_id=project.id, requirement_id=uuid4())
    spec_repo.save(spec)

    # Add version and approve it
    v1 = spec_repo.create_version_atomic(
        specification_id=spec.id,
        structured_content={"step": 1},
        is_approved=True,
    )

    # Attempt to modify the approved version's content
    spec_domain = spec_repo.get(spec.id)
    assert spec_domain is not None
    spec_ver = spec_domain.get_version(v1.version_number)
    assert spec_ver is not None
    spec_ver.structured_content = {"step": 2, "mutated": True}

    with pytest.raises(ImmutableArtifactError):
        spec_repo.save(spec_domain)


def test_approved_and_deployed_workflow_version_immutability_in_repository(memory_db):
    wf_repo = WorkflowRepository(memory_db)
    proj_repo = ProjectRepository(memory_db)

    project = proj_repo.save(Project(name="TestProj2"))
    wf = Workflow(project_id=project.id, name="TestWorkflow")
    wf_repo.save(wf)

    # Add version
    v1 = wf_repo.create_version_atomic(
        workflow_id=wf.id,
        specification_version_id=uuid4(),
        definition={"nodes": [1]},
    )

    # Approve and deploy
    v1.validate()
    v1.mark_tested()
    v1.mark_approved()
    v1.mark_deployed()

    # Save approved/deployed status
    wf_domain = wf_repo.get(wf.id)
    assert wf_domain is not None
    cur_ver = wf_domain.get_version(v1.id)
    assert cur_ver is not None
    cur_ver.status = WorkflowVersionStatus.DEPLOYED
    wf_repo.save(wf_domain)

    # Now attempt to mutate definition of the deployed version
    wf_domain = wf_repo.get(wf.id)
    assert wf_domain is not None
    cur_ver = wf_domain.get_version(v1.id)
    assert cur_ver is not None
    cur_ver.definition = {"nodes": [1, 2, "injected"]}

    with pytest.raises(ImmutableArtifactError):
        wf_repo.save(wf_domain)


def test_audit_repository_is_append_only():
    """Verify that AuditRepository does not expose update or delete methods."""
    assert not hasattr(AuditRepository, "update")
    assert not hasattr(AuditRepository, "delete")
    assert not hasattr(AuditRepository, "modify")
    assert hasattr(AuditRepository, "append")
    assert hasattr(AuditRepository, "get")
    assert hasattr(AuditRepository, "list_for_target")
