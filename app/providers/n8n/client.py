"""Production-hardened HTTP client for n8n REST API and Webhooks."""

import logging
import time
from typing import Any, Dict, List, Optional
import httpx

from app.core.config import get_settings
from app.core.logging import correlation_id_ctx
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
    UnknownProviderError,
    UnsupportedOperationError,
    sanitize_error_message,
)

logger = logging.getLogger(__name__)


class N8nClient:
    """Production-grade HTTP client interacting with n8n REST API and Webhook endpoints."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: Optional[float] = None,
        verify_ssl: Optional[bool] = None,
        max_retries: int = 2,
    ) -> None:
        settings = get_settings()
        self.base_url = (base_url or settings.n8n_url).rstrip("/")
        self.api_key = api_key if api_key is not None else settings.get_n8n_api_key_str()
        self.timeout_seconds = timeout or settings.n8n_timeout_seconds
        self.verify_ssl = verify_ssl if verify_ssl is not None else settings.n8n_verify_ssl
        self.max_retries = max_retries

    def _get_timeout(self) -> httpx.Timeout:
        return httpx.Timeout(
            connect=5.0,
            read=self.timeout_seconds,
            write=self.timeout_seconds,
            pool=5.0,
        )

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "application/json",
            "User-Agent": "AAE-Core/0.1.0",
        }
        if self.api_key:
            headers["X-N8N-API-KEY"] = self.api_key
        cid = correlation_id_ctx.get()
        if cid:
            headers["X-Correlation-ID"] = cid
        return headers

    def _handle_response_status(self, response: httpx.Response, url: str) -> None:
        """Translate HTTP status codes to typed, normalized ProviderError exceptions."""
        status = response.status_code
        if status < 400:
            return

        # Attempt to parse error detail from response
        error_msg = f"HTTP {status} on {url}"
        try:
            body = response.json()
            if isinstance(body, dict):
                error_msg = body.get("message") or body.get("error") or str(body)
        except Exception:
            text = response.text[:200]
            if text:
                error_msg = f"HTTP {status}: {text}"

        error_msg = sanitize_error_message(error_msg)

        if status == 401:
            raise ProviderAuthenticationError(f"Authentication failed: {error_msg}", status_code=status)
        elif status == 403:
            raise ProviderAuthorizationError(f"Authorization denied: {error_msg}", status_code=status)
        elif status == 404:
            raise ProviderNotFoundError(f"Resource not found: {error_msg}", status_code=status)
        elif status == 405:
            raise UnsupportedOperationError(f"Operation not supported by n8n: {error_msg}", status_code=status)
        elif status == 409:
            raise ProviderConflictError(f"Resource conflict: {error_msg}", status_code=status)
        elif status in (400, 422):
            raise ProviderValidationError(f"Validation failure: {error_msg}", status_code=status)
        elif status == 429:
            raise ProviderRateLimitError(f"Rate limit exceeded: {error_msg}", status_code=status)
        elif status in (502, 503, 504):
            raise ProviderUnavailableError(f"n8n instance unavailable: {error_msg}", status_code=status)
        else:
            raise ProviderError(f"n8n server error: {error_msg}", status_code=status)

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        is_retryable: bool = False,
    ) -> Any:
        """Execute HTTP request with error normalization and safe idempotent retry logic."""
        url = f"{self.base_url}/{path.lstrip('/')}"
        headers = self._get_headers()
        timeout = self._get_timeout()

        attempts = 1 + (self.max_retries if is_retryable else 0)
        last_exception: Optional[Exception] = None

        for attempt in range(1, attempts + 1):
            try:
                with httpx.Client(timeout=timeout, verify=self.verify_ssl) as client:
                    resp = client.request(
                        method=method,
                        url=url,
                        params=params,
                        json=json_data,
                        headers=headers,
                    )
                    self._handle_response_status(resp, url)
                    if resp.status_code == 204:
                        return None
                    try:
                        return resp.json()
                    except Exception:
                        return {"text": resp.text}
            except (httpx.ConnectError, httpx.ConnectTimeout) as e:
                last_exception = ProviderConnectionError(
                    f"Connection failed to n8n at {self.base_url}: {type(e).__name__}"
                )
                logger.warning(
                    "Connection attempt %d/%d to %s failed: %s",
                    attempt,
                    attempts,
                    path,
                    type(e).__name__,
                )
            except httpx.ReadTimeout as e:
                last_exception = ProviderTimeoutError(
                    f"Read timeout after {self.timeout_seconds}s querying n8n {path}"
                )
                logger.warning("Timeout attempt %d/%d on %s", attempt, attempts, path)
            except ProviderError:
                raise
            except Exception as e:
                raise UnknownProviderError(f"Unexpected provider client failure: {type(e).__name__}: {str(e)}") from e

            if attempt < attempts:
                time.sleep(0.5 * attempt)

        if last_exception:
            raise last_exception
        raise UnknownProviderError("Request failed without specific exception")

    # Instance & Health

    def check_connectivity(self) -> bool:
        """Verify network connectivity to n8n instance."""
        try:
            with httpx.Client(timeout=self._get_timeout(), verify=self.verify_ssl) as client:
                resp = client.get(self.base_url)
                return resp.status_code in (200, 301, 302)
        except Exception as e:
            logger.warning("n8n connectivity check failed: %s", type(e).__name__)
            return False

    def get_instance_info(self) -> Dict[str, Any]:
        """Fetch n8n version and instance health."""
        # Try /api/v1/health or fall back to base URL check
        try:
            return self._request("GET", "/api/v1/health", is_retryable=True)
        except ProviderNotFoundError:
            # Fall back to root status
            is_up = self.check_connectivity()
            return {"status": "ok" if is_up else "unreachable", "version": "2.38.7"}

    # Workflow Management

    def list_workflows(
        self,
        limit: int = 50,
        cursor: Optional[str] = None,
        active: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """List workflows via GET /api/v1/workflows."""
        params: Dict[str, Any] = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        if active is not None:
            params["active"] = "true" if active else "false"
        return self._request("GET", "/api/v1/workflows", params=params, is_retryable=True)

    def get_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """Fetch workflow by ID via GET /api/v1/workflows/{id}."""
        return self._request("GET", f"/api/v1/workflows/{workflow_id}", is_retryable=True)

    def create_workflow(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create new workflow via POST /api/v1/workflows."""
        return self._request("POST", "/api/v1/workflows", json_data=payload, is_retryable=False)

    def update_workflow(self, workflow_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Update workflow via PUT /api/v1/workflows/{id}."""
        return self._request("PUT", f"/api/v1/workflows/{workflow_id}", json_data=payload, is_retryable=False)

    def activate_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """Activate workflow via POST /api/v1/workflows/{id}/activate."""
        return self._request("POST", f"/api/v1/workflows/{workflow_id}/activate", is_retryable=False)

    def deactivate_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """Deactivate workflow via POST /api/v1/workflows/{id}/deactivate."""
        return self._request("POST", f"/api/v1/workflows/{workflow_id}/deactivate", is_retryable=False)

    def delete_workflow(self, workflow_id: str) -> bool:
        """Delete workflow via DELETE /api/v1/workflows/{id}."""
        self._request("DELETE", f"/api/v1/workflows/{workflow_id}", is_retryable=False)
        return True

    # Execution History & Management

    def list_executions(
        self,
        workflow_id: Optional[str] = None,
        limit: int = 20,
        cursor: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List execution records via GET /api/v1/executions."""
        params: Dict[str, Any] = {"limit": limit}
        if workflow_id:
            params["workflowId"] = workflow_id
        if cursor:
            params["cursor"] = cursor
        if status:
            params["status"] = status
        return self._request("GET", "/api/v1/executions", params=params, is_retryable=True)

    def get_execution(self, execution_id: str) -> Dict[str, Any]:
        """Fetch execution details via GET /api/v1/executions/{id}."""
        return self._request("GET", f"/api/v1/executions/{execution_id}", is_retryable=True)

    def retry_execution(self, execution_id: str) -> Dict[str, Any]:
        """Retry failed execution via POST /api/v1/executions/{id}/retry."""
        return self._request("POST", f"/api/v1/executions/{execution_id}/retry", is_retryable=False)

    # Webhook Trigger (Workaround N8N-WA-001)

    def trigger_webhook(
        self,
        webhook_path: str,
        payload: Optional[Dict[str, Any]] = None,
        method: str = "POST",
    ) -> Dict[str, Any]:
        """Trigger an n8n webhook (Workaround N8N-WA-001)."""
        clean_path = webhook_path.lstrip("/")
        return self._request(
            method=method.upper(),
            path=f"/webhook/{clean_path}",
            json_data=payload if method.upper() in ("POST", "PUT", "PATCH") else None,
            params=payload if method.upper() == "GET" else None,
            is_retryable=False,
        )
