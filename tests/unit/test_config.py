"""Unit tests for configuration management."""

import pytest
from pydantic import ValidationError
from app.core.config import Settings


def test_settings_defaults():
    settings = Settings()
    assert settings.app_name == "AI Automation Engineer"
    assert settings.app_version == "0.1.0"
    assert settings.environment == "development"
    assert settings.n8n_url == "http://localhost:5678"


def test_settings_invalid_environment():
    with pytest.raises(ValidationError):
        Settings(environment="invalid_env")


def test_settings_safe_dict_redaction():
    settings = Settings(
        secret_key="my_super_secret_signing_key_12345",
        database_url="postgresql+psycopg://myuser:supersecretpass@localhost:5432/mydb",
        n8n_api_key="n8n_api_secret_key_9876",
    )
    safe = settings.safe_dict()
    assert safe["secret_key"] == "********"
    assert "supersecretpass" not in safe["database_url"]
    assert "********" in safe["database_url"]
    assert safe["n8n_api_key"] == "********"


def test_settings_repr_hides_secrets():
    settings = Settings(secret_key="secret123")
    repr_str = repr(settings)
    assert "secret123" not in repr_str
    assert "Settings" in repr_str
