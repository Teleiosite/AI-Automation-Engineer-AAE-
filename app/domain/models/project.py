"""Project domain entity."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4
from app.domain.errors import DomainValidationError


@dataclass
class Project:
    """Project boundary container."""
    name: str
    id: UUID = field(default_factory=uuid4)
    description: str = ""
    is_active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise DomainValidationError("Project name cannot be empty")
        if self.created_at.tzinfo is None:
            raise DomainValidationError("Timestamps must be timezone-aware UTC")
