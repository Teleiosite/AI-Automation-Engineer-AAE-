"""Unit tests for logging and secret redaction."""

import json
import logging
from app.core.logging import JSONLogFormatter, correlation_id_ctx, redact_secrets


def test_redact_secrets_passwords():
    raw = "Connecting with password: my_password123 to database"
    sanitized = redact_secrets(raw)
    assert "my_password123" not in sanitized
    assert "********" in sanitized


def test_redact_secrets_api_keys():
    raw = "Sending request with api_key=abc123secret456 in header"
    sanitized = redact_secrets(raw)
    assert "abc123secret456" not in sanitized
    assert "********" in sanitized


def test_redact_secrets_bearer_token():
    raw = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    sanitized = redact_secrets(raw)
    assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in sanitized
    assert "********" in sanitized


def test_redact_database_url_passwords():
    raw = "Connecting to postgresql://admin:super_secret_db_pass@localhost:5432/aae"
    sanitized = redact_secrets(raw)
    assert "super_secret_db_pass" not in sanitized
    assert "********" in sanitized


def test_json_formatter_with_correlation_id():
    token = correlation_id_ctx.set("corr-test-uuid-1234")
    try:
        formatter = JSONLogFormatter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname=__file__,
            lineno=10,
            msg="User login with token: secret_token_xyz",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        log_json = json.loads(output)
        assert log_json["correlation_id"] == "corr-test-uuid-1234"
        assert log_json["level"] == "INFO"
        assert "secret_token_xyz" not in log_json["message"]
        assert "********" in log_json["message"]
    finally:
        correlation_id_ctx.reset(token)
