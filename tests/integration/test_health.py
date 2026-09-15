"""Integration tests for health and readiness endpoints."""

from unittest.mock import patch
from fastapi.testclient import TestClient


def test_health_endpoint(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["version"] == "0.1.0"
    assert "environment" in data


def test_request_correlation_id_middleware(client: TestClient):
    custom_cid = "client-trace-12345"
    response = client.get("/health", headers={"X-Request-ID": custom_cid})
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == custom_cid


def test_readiness_endpoint_connected(client: TestClient):
    with patch("app.api.routes.health.check_database_connection", return_value=(True, "connected")), \
         patch("app.api.routes.health.N8nClient.check_connectivity", return_value=True):
        response = client.get("/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert data["components"]["database"]["status"] == "connected"
        assert data["components"]["n8n"]["status"] == "connected"


def test_readiness_endpoint_degraded_when_db_down(client: TestClient):
    with patch("app.api.routes.health.check_database_connection", return_value=(False, "unreachable")), \
         patch("app.api.routes.health.N8nClient.check_connectivity", return_value=True):
        response = client.get("/ready")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "degraded"
        assert data["components"]["database"]["status"] == "unreachable"
        assert data["components"]["n8n"]["status"] == "connected"
