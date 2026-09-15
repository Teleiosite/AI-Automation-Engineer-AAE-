"""Capability Repository interface and in-memory implementation."""

import threading
from typing import Dict, List, Optional

from app.domain.capabilities.models import (
    Capability,
    CapabilityRegistry,
    CapabilityStatus,
    get_default_n8n_registry,
)


class CapabilityRepository:
    """Thread-safe in-memory repository managing provider capabilities."""

    def __init__(self, initial_registry: Optional[CapabilityRegistry] = None) -> None:
        self._lock = threading.RLock()
        self._storage: Dict[str, Capability] = {}
        registry = initial_registry or get_default_n8n_registry()
        for cap in registry.list_all():
            self._storage[cap.name] = cap

    def get(self, name: str) -> Optional[Capability]:
        """Fetch capability by name."""
        with self._lock:
            return self._storage.get(name)

    def save(self, capability: Capability) -> None:
        """Store or update a capability."""
        with self._lock:
            self._storage[capability.name] = capability

    def list_all(self) -> List[Capability]:
        """Retrieve all stored capabilities."""
        with self._lock:
            return list(self._storage.values())

    def list_by_provider(self, provider: str, version: Optional[str] = None) -> List[Capability]:
        """Filter capabilities by provider name and optional version."""
        with self._lock:
            return [
                c for c in self._storage.values()
                if c.provider == provider and (version is None or c.provider_version == version)
            ]

    def list_by_status(self, status: CapabilityStatus) -> List[Capability]:
        """Filter capabilities by status."""
        with self._lock:
            return [c for c in self._storage.values() if c.status == status]

    def delete(self, name: str) -> bool:
        """Remove a capability by name."""
        with self._lock:
            if name in self._storage:
                del self._storage[name]
                return True
            return False

    def to_registry(self) -> CapabilityRegistry:
        """Export current storage state as a CapabilityRegistry."""
        with self._lock:
            reg = CapabilityRegistry()
            for cap in self._storage.values():
                reg.register(cap)
            return reg
