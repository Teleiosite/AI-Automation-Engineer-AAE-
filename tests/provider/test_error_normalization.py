"""Tests for provider error normalization and credential sanitization."""

import pytest
from app.providers.errors import (
    ProviderAuthenticationError,
    ProviderAuthorizationError,
    ProviderConflictError,
    ProviderConnectionError,
    ProviderError,
    ProviderNotFoundError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    ProviderValidationError,
    UnsupportedOperationError,
    sanitize_error_message,
)


def test_sanitize_error_message_masks_api_key():
    raw = "Failed with api_key=secret12345 in query string"
    sanitized = sanitize_error_message(raw)
    assert "secret12345" not in sanitized
    assert "api_key=********" in sanitized


def test_sanitize_error_message_masks_bearer_token():
    raw = "Authorization failed: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.invalid"
    sanitized = sanitize_error_message(raw)
    assert "eyJhbGci" not in sanitized
    assert "Bearer ********" in sanitized


def test_sanitize_error_message_masks_header():
    raw = "Headers included X-N8N-API-KEY: n8n_sec_key_xyz890"
    sanitized = sanitize_error_message(raw)
    assert "n8n_sec_key_xyz890" not in sanitized
    assert "X-N8N-API-KEY: ********" in sanitized


def test_provider_error_hierarchy_sanitizes_message():
    err = ProviderAuthenticationError("Invalid credentials password=SuperSecretPassword123!")
    assert "SuperSecretPassword123!" not in str(err)
    assert "password=********" in str(err)
    assert isinstance(err, ProviderError)


def test_provider_error_subclasses():
    assert issubclass(ProviderAuthenticationError, ProviderError)
    assert issubclass(ProviderAuthorizationError, ProviderError)
    assert issubclass(ProviderNotFoundError, ProviderError)
    assert issubclass(ProviderValidationError, ProviderError)
    assert issubclass(ProviderConflictError, ProviderError)
    assert issubclass(ProviderRateLimitError, ProviderError)
    assert issubclass(ProviderTimeoutError, ProviderError)
    assert issubclass(ProviderConnectionError, ProviderError)
    assert issubclass(ProviderUnavailableError, ProviderError)
    assert issubclass(UnsupportedOperationError, ProviderError)
