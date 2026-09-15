"""Security and production hardening tests (Phase 22 / §41, §44, §45 AAE Security Policy)."""

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.security import (
    IdempotencyGuard,
    RateLimiter,
    SSRFProtectionError,
    validate_safe_url,
)
from app.main import create_app


def test_ssrf_protection_blocks_localhost_and_private_networks():
    """Verify SSRF protection rejects loopback, private ranges, metadata, and invalid schemes."""
    # Localhost
    with pytest.raises(SSRFProtectionError, match="Targeting localhost"):
        validate_safe_url("http://localhost:8080/api")
    with pytest.raises(SSRFProtectionError, match="Targeting localhost"):
        validate_safe_url("http://127.0.0.1:5432")

    # Cloud instance metadata service
    with pytest.raises(SSRFProtectionError, match="metadata"):
        validate_safe_url("http://169.254.169.254/latest/meta-data/")

    # RFC 1918 private subnets
    with pytest.raises(SSRFProtectionError, match="private, loopback, or reserved"):
        validate_safe_url("http://10.0.0.5/admin")
    with pytest.raises(SSRFProtectionError, match="private, loopback, or reserved"):
        validate_safe_url("https://192.168.1.1/setup")
    with pytest.raises(SSRFProtectionError, match="private, loopback, or reserved"):
        validate_safe_url("https://172.16.1.100/status")

    # Disallowed schemes
    with pytest.raises(SSRFProtectionError, match="Scheme 'file' is not permitted"):
        validate_safe_url("file:///etc/passwd")
    with pytest.raises(SSRFProtectionError, match="Scheme 'ftp' is not permitted"):
        validate_safe_url("ftp://ftp.example.com/data")


def test_ssrf_protection_allows_valid_public_urls():
    """Verify SSRF validation accepts legitimate public endpoints."""
    assert validate_safe_url("https://api.github.com/v1/repos") is True
    assert validate_safe_url("https://hooks.slack.com/services/T00/B00/X00") is True
    assert validate_safe_url("http://api.stripe.com/v1/charges") is True


def test_rate_limiter_sliding_window():
    """Verify RateLimiter enforces limits within window and resets."""
    limiter = RateLimiter(max_requests=3, window_seconds=10.0)
    key = "client-ip-123"

    assert limiter.is_allowed(key) is True
    assert limiter.is_allowed(key) is True
    assert limiter.is_allowed(key) is True
    # 4th request exceeds max_requests=3
    assert limiter.is_allowed(key) is False

    # Reset clears records
    limiter.reset()
    assert limiter.is_allowed(key) is True


def test_idempotency_guard_replay_prevention():
    """Verify IdempotencyGuard blocks duplicate action execution."""
    guard = IdempotencyGuard(ttl_seconds=60.0)
    key = "idem-tx-999"

    # Initial submission is accepted
    assert guard.check_and_record(key) is True
    # Immediate replay is rejected
    assert guard.check_and_record(key) is False

    # Different key is accepted
    assert guard.check_and_record("idem-tx-1000") is True


def test_api_security_headers_middleware():
    """Verify all mandatory security headers are set on HTTP responses."""
    app = create_app()
    client = TestClient(app)

    response = client.get("/health")
    assert response.status_code == 200

    headers = response.headers
    assert headers.get("X-Content-Type-Options") == "nosniff"
    assert headers.get("X-Frame-Options") == "DENY"
    assert headers.get("X-XSS-Protection") == "1; mode=block"
    assert "default-src 'none'" in headers.get("Content-Security-Policy", "")


def test_api_rate_limiting_middleware():
    """Verify API returns HTTP 429 when client bursts excessive requests."""
    app = create_app()
    client = TestClient(app)

    # Issue 130 requests (threshold is 120 req/min)
    status_codes = [client.get("/health").status_code for _ in range(130)]
    assert 429 in status_codes
    assert status_codes[-1] == 429


def test_production_environment_disables_docs(monkeypatch):
    """Verify OpenAPI and Swagger UI docs are disabled in production mode."""
    from app.core.config import get_settings
    monkeypatch.setenv("AAE_ENVIRONMENT", "production")
    monkeypatch.setenv("AAE_DEBUG", "false")
    monkeypatch.setenv("AAE_SECRET_KEY", "prod_super_secure_key_12345678901234567890")
    get_settings.cache_clear()

    # Recreate app under production environment
    prod_app = create_app()
    client = TestClient(prod_app)

    # In production, docs should return 404
    docs_resp = client.get("/docs")
    assert docs_resp.status_code == 404

    redoc_resp = client.get("/redoc")
    assert redoc_resp.status_code == 404

    # Cleanup settings cache after test
    get_settings.cache_clear()
