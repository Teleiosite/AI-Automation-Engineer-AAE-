"""Security baseline tests."""

from fastapi.testclient import TestClient
from app.core.config import Settings
from app.core.security import mask_secret, redact_sensitive_dict


def test_mask_secret_utility():
    assert mask_secret("") == ""
    assert mask_secret("short") == "********"
    assert mask_secret("super_long_secret_value_12345", prefix_len=3, suffix_len=3) == "sup********345"


def test_redact_sensitive_dict():
    data = {
        "user": "developer",
        "api_key": "secret-12345",
        "nested": {
            "password": "db_password",
            "normal_field": "visible_value"
        },
        "tokens": [
            {"token": "tok-abc", "id": 1}
        ]
    }
    redacted = redact_sensitive_dict(data)
    assert redacted["user"] == "developer"
    assert redacted["api_key"] == "********"
    assert redacted["nested"]["password"] == "********"
    assert redacted["nested"]["normal_field"] == "visible_value"
    assert redacted["tokens"][0]["token"] == "********"
    assert redacted["tokens"][0]["id"] == 1


def test_no_secrets_in_health_or_ready_output(client: TestClient):
    resp_health = client.get("/health")
    assert resp_health.status_code == 200
    content = resp_health.text
    assert "password" not in content.lower()
    assert "secret" not in content.lower()
    assert "api_key" not in content.lower()

    resp_ready = client.get("/ready")
    content_ready = resp_ready.text
    assert "password" not in content_ready.lower()
    assert "postgres:" not in content_ready.lower()
