"""Tests for N8nClient HTTP requests, status normalization, and retry behavior."""

from unittest.mock import MagicMock, patch
import httpx
import pytest

from app.providers.errors import (
    ProviderAuthenticationError,
    ProviderAuthorizationError,
    ProviderConflictError,
    ProviderConnectionError,
    ProviderNotFoundError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    ProviderValidationError,
    UnsupportedOperationError,
)
from app.providers.n8n.client import N8nClient


@pytest.fixture
def client():
    return N8nClient(base_url="http://localhost:5678", api_key="test-key-123", timeout=2.0, max_retries=1)


def test_client_headers_include_api_key_and_user_agent(client):
    headers = client._get_headers()
    assert headers["X-N8N-API-KEY"] == "test-key-123"
    assert headers["User-Agent"] == "AAE-Core/0.1.0"
    assert headers["Accept"] == "application/json"


@patch("httpx.Client.request")
def test_client_status_401_raises_authentication_error(mock_request, client):
    mock_request.return_value = httpx.Response(
        401,
        json={"message": "Unauthorized: invalid API key"},
        request=httpx.Request("GET", "http://localhost:5678/api/v1/workflows"),
    )
    with pytest.raises(ProviderAuthenticationError) as exc_info:
        client.list_workflows()
    assert "Unauthorized" in str(exc_info.value)
    assert exc_info.value.status_code == 401


@patch("httpx.Client.request")
def test_client_status_403_raises_authorization_error(mock_request, client):
    mock_request.return_value = httpx.Response(
        403,
        json={"message": "Forbidden access"},
        request=httpx.Request("GET", "http://localhost:5678/api/v1/workflows"),
    )
    with pytest.raises(ProviderAuthorizationError) as exc_info:
        client.list_workflows()
    assert "Forbidden" in str(exc_info.value)
    assert exc_info.value.status_code == 403


@patch("httpx.Client.request")
def test_client_status_404_raises_not_found_error(mock_request, client):
    mock_request.return_value = httpx.Response(
        404,
        json={"message": "Workflow 999 not found"},
        request=httpx.Request("GET", "http://localhost:5678/api/v1/workflows/999"),
    )
    with pytest.raises(ProviderNotFoundError) as exc_info:
        client.get_workflow("999")
    assert "not found" in str(exc_info.value)
    assert exc_info.value.status_code == 404


@patch("httpx.Client.request")
def test_client_status_405_raises_unsupported_operation_error(mock_request, client):
    mock_request.return_value = httpx.Response(
        405,
        text="Method Not Allowed",
        request=httpx.Request("POST", "http://localhost:5678/api/v1/workflows/123/run"),
    )
    with pytest.raises(UnsupportedOperationError) as exc_info:
        client._request("POST", "/api/v1/workflows/123/run")
    assert "Operation not supported" in str(exc_info.value)
    assert exc_info.value.status_code == 405


@patch("httpx.Client.request")
def test_client_status_409_raises_conflict_error(mock_request, client):
    mock_request.return_value = httpx.Response(
        409,
        json={"message": "Workflow with name already exists"},
        request=httpx.Request("POST", "http://localhost:5678/api/v1/workflows"),
    )
    with pytest.raises(ProviderConflictError) as exc_info:
        client.create_workflow({"name": "Duplicate"})
    assert "conflict" in str(exc_info.value).lower()
    assert exc_info.value.status_code == 409


@patch("httpx.Client.request")
def test_client_status_422_raises_validation_error(mock_request, client):
    mock_request.return_value = httpx.Response(
        422,
        json={"message": "Invalid node parameter schema"},
        request=httpx.Request("POST", "http://localhost:5678/api/v1/workflows"),
    )
    with pytest.raises(ProviderValidationError) as exc_info:
        client.create_workflow({"nodes": []})
    assert "Validation failure" in str(exc_info.value)
    assert exc_info.value.status_code == 422


@patch("httpx.Client.request")
def test_client_status_429_raises_rate_limit_error(mock_request, client):
    mock_request.return_value = httpx.Response(
        429,
        json={"message": "Too many requests, slow down"},
        request=httpx.Request("GET", "http://localhost:5678/api/v1/workflows"),
    )
    with pytest.raises(ProviderRateLimitError) as exc_info:
        client.list_workflows()
    assert "Rate limit exceeded" in str(exc_info.value)
    assert exc_info.value.status_code == 429


@patch("httpx.Client.request")
def test_client_status_503_raises_unavailable_error(mock_request, client):
    mock_request.return_value = httpx.Response(
        503,
        text="Service Unavailable",
        request=httpx.Request("GET", "http://localhost:5678/api/v1/workflows"),
    )
    with pytest.raises(ProviderUnavailableError) as exc_info:
        client.list_workflows()
    assert "unavailable" in str(exc_info.value).lower()
    assert exc_info.value.status_code == 503


@patch("httpx.Client.request")
def test_client_connection_error_mapping_and_retry(mock_request, client):
    # Simulate ConnectError on first attempt, then success on retry
    mock_request.side_effect = [
        httpx.ConnectError("Connection refused", request=httpx.Request("GET", "http://localhost:5678/api/v1/workflows")),
        httpx.Response(200, json={"data": []}, request=httpx.Request("GET", "http://localhost:5678/api/v1/workflows")),
    ]
    result = client.list_workflows()
    assert result == {"data": []}
    assert mock_request.call_count == 2


@patch("httpx.Client.request")
def test_client_non_idempotent_post_does_not_retry_on_failure(mock_request, client):
    # Non-retryable POST should fail immediately without retrying
    mock_request.side_effect = httpx.ConnectError(
        "Connection refused",
        request=httpx.Request("POST", "http://localhost:5678/api/v1/workflows"),
    )
    with pytest.raises(ProviderConnectionError):
        client.create_workflow({"name": "New Workflow"})
    assert mock_request.call_count == 1
