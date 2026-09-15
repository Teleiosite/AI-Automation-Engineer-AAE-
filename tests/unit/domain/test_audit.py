"""Unit tests for AuditEvent and secret sanitization."""

from uuid import uuid4
from app.domain.models.audit import AuditEvent, sanitize_audit_metadata


def test_sanitize_audit_metadata():
    raw_meta = {
        "user": "dev",
        "api_key": "raw_secret_key_12345",
        "nested": {
            "password": "db_password_xyz",
            "normal": "value"
        },
        "tokens": [
            {"token": "secret_bearer_token"}
        ]
    }
    clean = sanitize_audit_metadata(raw_meta)
    assert clean["user"] == "dev"
    assert clean["api_key"] == "********"
    assert clean["nested"]["password"] == "********"
    assert clean["nested"]["normal"] == "value"
    assert clean["tokens"][0]["token"] == "********"


def test_audit_event_creation_sanitizes_metadata():
    event = AuditEvent(
        event_type="WORKFLOW_DEPLOYED",
        actor="deploy_agent",
        target_type="Workflow",
        target_id=str(uuid4()),
        metadata={"db_password": "super_secret_pw", "version": 1},
    )
    assert event.event_type == "WORKFLOW_DEPLOYED"
    assert event.metadata["db_password"] == "********"
    assert event.metadata["version"] == 1
