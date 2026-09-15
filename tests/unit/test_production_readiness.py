"""Production readiness and packaging unit tests (Phase 23)."""

from pathlib import Path
import pytest

from app.core.config import Settings


def test_dockerfile_security_and_best_practices():
    """Verify Dockerfile adheres to security guidelines (non-root user, healthcheck, multi-stage)."""
    dockerfile_path = Path("Dockerfile")
    assert dockerfile_path.exists(), "Dockerfile must exist in root directory"

    content = dockerfile_path.read_text(encoding="utf-8")

    # Multi-stage build
    assert "AS builder" in content
    assert "AS runtime" in content

    # Non-root unprivileged user
    assert "useradd" in content
    assert "USER aae" in content

    # Healthcheck instruction
    assert "HEALTHCHECK" in content
    assert "/health" in content

    # Correct entrypoint
    assert 'ENTRYPOINT ["uvicorn", "app.main:app"' in content


def test_docker_compose_production_structure():
    """Verify production compose file specifies healthy dependencies, security options, and persistent storage."""
    compose_path = Path("docker-compose.prod.yml")
    assert compose_path.exists(), "docker-compose.prod.yml must exist"

    content = compose_path.read_text(encoding="utf-8")

    # Services
    assert "aae-api:" in content
    assert "postgres:" in content

    # Service health dependency
    assert "condition: service_healthy" in content

    # Security options
    assert "no-new-privileges:true" in content

    # Production environment variables
    assert "AAE_ENVIRONMENT: production" in content
    assert 'AAE_DEBUG: "false"' in content

    # Persistent storage volume
    assert "postgres_data:" in content


def test_production_settings_enforces_secure_secret_key():
    """Verify that deploying to production with default dev credentials is rejected at startup."""
    # Insecure default key in production must fail
    with pytest.raises(ValueError, match="Production environment requires a secure secret_key"):
        Settings(
            environment="production",
            secret_key="dev_insecure_secret_key_change_in_production_min_32_chars",
        )

    # Key under 32 chars in production must fail
    with pytest.raises(ValueError, match="at least 32 characters"):
        Settings(
            environment="production",
            secret_key="short_key_123",
        )

    # Valid production key of 32+ characters succeeds
    prod_settings = Settings(
        environment="production",
        secret_key="prod_super_secure_vault_secret_key_32_chars_long_minimum",
    )
    assert prod_settings.environment == "production"
