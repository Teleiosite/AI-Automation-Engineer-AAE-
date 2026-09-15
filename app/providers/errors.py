"""Provider error normalization hierarchy."""

import re
from typing import Optional


def sanitize_error_message(message: str) -> str:
    """Scrub potential credentials, API keys, and bearer tokens from error strings."""
    # Mask API key query params or header values
    cleaned = re.sub(r"(api[_-]?key|token|secret|password)=([^\s&]+)", r"\1=********", message, flags=re.IGNORECASE)
    cleaned = re.sub(r"(Bearer\s+)[A-Za-z0-9\-._~+/]+=*", r"\1********", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"(X-N8N-API-KEY:\s*)[^\s]+", r"\1********", cleaned, flags=re.IGNORECASE)
    return cleaned


class ProviderError(Exception):
    """Base exception for all provider operations."""

    def __init__(self, message: str, provider: str = "n8n", status_code: Optional[int] = None) -> None:
        self.raw_message = message
        self.sanitized_message = sanitize_error_message(message)
        self.provider = provider
        self.status_code = status_code
        super().__init__(self.sanitized_message)


class ProviderAuthenticationError(ProviderError):
    """Raised when authentication with provider fails (e.g. invalid API key, 401)."""
    pass


class ProviderAuthorizationError(ProviderError):
    """Raised when permissions are insufficient for an action (403)."""
    pass


class ProviderNotFoundError(ProviderError):
    """Raised when the requested provider resource is not found (404)."""
    pass


class ProviderValidationError(ProviderError):
    """Raised when provider payload or schema validation fails (400, 422)."""
    pass


class ProviderConflictError(ProviderError):
    """Raised when resource conflict occurs (e.g. duplicate name, concurrent edit, 409)."""
    pass


class ProviderRateLimitError(ProviderError):
    """Raised when provider rate limits are exceeded (429)."""
    pass


class ProviderTimeoutError(ProviderError):
    """Raised when network or operation timeout expires."""
    pass


class ProviderConnectionError(ProviderError):
    """Raised when provider network connection fails or host is unreachable."""
    pass


class ProviderUnavailableError(ProviderError):
    """Raised when provider returns 502/503/504 or is in maintenance."""
    pass


class UnsupportedOperationError(ProviderError):
    """Raised when an operation is not supported by the provider engine."""
    pass


class CapabilityLimitationError(UnsupportedOperationError):
    """Raised when an operation cannot be performed due to documented provider limitations."""
    pass


class ProviderVersionError(ProviderError):
    """Raised when provider version is incompatible with required features."""
    pass


class ProviderExecutionError(ProviderError):
    """Raised when workflow execution encounters an unrecoverable runtime error."""
    pass


class UnknownProviderError(ProviderError):
    """Raised when an unexpected provider failure occurs."""
    pass
