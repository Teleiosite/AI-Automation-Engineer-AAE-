"""Security utilities for credential masking, redaction, and sanitization."""

from typing import Any, Dict


def mask_secret(value: str, prefix_len: int = 0, suffix_len: int = 0) -> str:
    """Mask a sensitive string with asterisks."""
    if not value:
        return ""
    if len(value) <= (prefix_len + suffix_len):
        return "********"
    prefix = value[:prefix_len] if prefix_len > 0 else ""
    suffix = value[-suffix_len:] if suffix_len > 0 else ""
    return f"{prefix}********{suffix}"


def redact_sensitive_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively redacts sensitive keys in a dictionary."""
    sensitive_patterns = ("password", "secret", "token", "api_key", "auth", "credential", "private_key")
    redacted = {}
    for k, v in data.items():
        k_lower = k.lower()
        if isinstance(v, dict):
            redacted[k] = redact_sensitive_dict(v)
        elif isinstance(v, list):
            redacted[k] = [
                redact_sensitive_dict(item)
                if isinstance(item, dict)
                else ("********" if any(s in k_lower for s in sensitive_patterns) else item)
                for item in v
            ]
        elif any(s in k_lower for s in sensitive_patterns):
            redacted[k] = "********"
        else:
            redacted[k] = v
    return redacted


import ipaddress
import time
from typing import List, Optional, Set
from urllib.parse import urlparse


class SSRFProtectionError(Exception):
    """Raised when an outbound URL violates SSRF safety boundaries (§45 AAE Security Policy)."""
    pass


def validate_safe_url(url: str, allowed_schemes: Optional[Set[str]] = None) -> bool:
    """Validate that a URL does not target localhost, link-local, or private RFC1918 addresses."""
    if not url or not url.strip():
        raise SSRFProtectionError("URL cannot be empty")

    parsed = urlparse(url.strip())
    schemes = allowed_schemes or {"http", "https"}
    if parsed.scheme.lower() not in schemes:
        raise SSRFProtectionError(f"Scheme '{parsed.scheme}' is not permitted. Allowed: {sorted(schemes)}")

    hostname = parsed.hostname
    if not hostname:
        raise SSRFProtectionError("URL must include a valid hostname")

    lowered = hostname.lower()
    if lowered in {"localhost", "localhost.localdomain", "127.0.0.1", "::1"}:
        raise SSRFProtectionError(f"Targeting localhost ('{hostname}') is strictly prohibited")

    if lowered == "169.254.169.254":
        raise SSRFProtectionError("Cloud instance metadata service access is forbidden")

    # Parse IP addresses
    try:
        ip = ipaddress.ip_address(hostname)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise SSRFProtectionError(f"IP address '{hostname}' belongs to a private, loopback, or reserved network")
    except ValueError:
        # Domain name checks
        restricted_substrings = ("localhost", "internal", "local", "169.254.169.254", "metadata")
        if any(sub in lowered for sub in restricted_substrings):
            raise SSRFProtectionError(f"Hostname '{hostname}' matches restricted internal namespace")

    return True


class RateLimiter:
    """Sliding-window in-memory rate limiter (§41 AAE Security Policy)."""

    def __init__(self, max_requests: int = 60, window_seconds: float = 60.0) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._records: Dict[str, List[float]] = {}

    def is_allowed(self, client_key: str) -> bool:
        """Check if client request is within rate limits; records timestamp if allowed."""
        now = time.time()
        window_start = now - self.window_seconds

        timestamps = self._records.get(client_key, [])
        valid_timestamps = [t for t in timestamps if t > window_start]

        if len(valid_timestamps) >= self.max_requests:
            self._records[client_key] = valid_timestamps
            return False

        valid_timestamps.append(now)
        self._records[client_key] = valid_timestamps
        return True

    def reset(self) -> None:
        self._records.clear()


class IdempotencyGuard:
    """In-memory idempotency deduplication cache with TTL (§44 AAE Security Policy)."""

    def __init__(self, ttl_seconds: float = 300.0) -> None:
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, float] = {}

    def check_and_record(self, key: str) -> bool:
        """Returns True if the key is novel (recorded). Returns False if duplicate replay attempt."""
        if not key:
            return True
        now = time.time()
        # Evict expired
        expired = [k for k, t in self._cache.items() if now - t > self.ttl_seconds]
        for k in expired:
            del self._cache[k]

        if key in self._cache:
            return False

        self._cache[key] = now
        return True

    def clear(self) -> None:
        self._cache.clear()

