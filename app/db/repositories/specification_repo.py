"""Specification repository adapter with concurrency-safe versioning."""

from typing import Any, Dict, Optional
from uuid import UUID, uuid4
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload
from app.db.mappers.specification_mapper import (
    specification_to_domain,
    specification_to_model,
    specification_version_to_domain,
    specification_version_to_model,
)
from app.db.models.specification import SpecificationModel, SpecificationVersionModel
from app.domain.errors import ImmutableArtifactError, InvariantViolationError
from app.domain.models.specification import Specification, SpecificationVersion


class SpecificationRepository:
    """Repository managing Specification aggregate and concurrency-safe version allocation."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, specification_id: UUID) -> Optional[Specification]:
        """Fetch specification aggregate with all its versions."""
        stmt = (
            select(SpecificationModel)
            .options(selectinload(SpecificationModel.versions))
            .where(SpecificationModel.id == specification_id)
        )
        model = self._session.execute(stmt).scalar_one_or_none()
        return specification_to_domain(model) if model else None

    def get_version(self, specification_id: UUID, version_number: int) -> Optional[SpecificationVersion]:
        """Fetch a specific version by specification ID and version number."""
        stmt = (
            select(SpecificationVersionModel)
            .where(
                SpecificationVersionModel.specification_id == specification_id,
                SpecificationVersionModel.version_number == version_number,
            )
        )
        model = self._session.execute(stmt).scalar_one_or_none()
        return specification_version_to_domain(model) if model else None

    def save(self, specification: Specification) -> Specification:
        """Persist or update Specification aggregate."""
        stmt = (
            select(SpecificationModel)
            .options(selectinload(SpecificationModel.versions))
            .where(SpecificationModel.id == specification.id)
        )
        model = self._session.execute(stmt).scalar_one_or_none()

        if model:
            model.status = specification.status.value
            model.current_version_number = specification.current_version_number

            # Check immutability on versions
            existing_vers = {v.version_number: v for v in model.versions}
            for domain_ver in specification.versions:
                if domain_ver.version_number in existing_vers:
                    m_ver = existing_vers[domain_ver.version_number]
                    if m_ver.is_approved and m_ver.structured_content != domain_ver.structured_content:
                        raise ImmutableArtifactError(
                            f"Specification version {m_ver.version_number} is approved and immutable"
                        )
                    m_ver.is_approved = domain_ver.is_approved
                    m_ver.structured_content = domain_ver.structured_content
                else:
                    new_m_ver = specification_version_to_model(domain_ver)
                    model.versions.append(new_m_ver)
        else:
            model = specification_to_model(specification)
            self._session.add(model)

        self._session.flush()
        return specification_to_domain(model)

    def create_version_atomic(
        self,
        specification_id: UUID,
        structured_content: Dict[str, Any],
        is_approved: bool = False,
    ) -> SpecificationVersion:
        """
        Concurrency-safe version allocation using row-level locking on the parent aggregate.
        Guarantees no duplicate committed version numbers for the same specification.
        """
        # 1. Lock the parent specification row
        stmt = (
            select(SpecificationModel)
            .where(SpecificationModel.id == specification_id)
            .with_for_update()
        )
        spec_model = self._session.execute(stmt).scalar_one_or_none()
        if not spec_model:
            raise InvariantViolationError(f"Specification '{specification_id}' does not exist")

        # 2. Determine next sequential version number under parent lock
        max_ver_stmt = select(func.max(SpecificationVersionModel.version_number)).where(
            SpecificationVersionModel.specification_id == specification_id
        )
        max_ver = self._session.execute(max_ver_stmt).scalar() or 0
        next_ver = max_ver + 1

        # 3. Insert new version
        ver_model = SpecificationVersionModel(
            id=uuid4(),
            specification_id=specification_id,
            version_number=next_ver,
            structured_content=structured_content,
            is_approved=is_approved,
        )
        self._session.add(ver_model)

        # 4. Update specification current version
        spec_model.current_version_number = next_ver
        self._session.flush()

        return specification_version_to_domain(ver_model)
