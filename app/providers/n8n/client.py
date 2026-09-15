"""HTTP client for n8n REST API and Webhooks."""

import logging
from typing import Any, Dict, List, Optional
import httpx
from app.core.config import get_settings
from app.core.logging import correlation_id_ctx
from app.providers.base import ProviderError

logger = logging.getLogger(__name__)


class N8nClient:
    """Client for interacting with an n8n 2.38.7 instance."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: Optional[float] = None,
        verify_ssl: Optional[bool] = None,
    ) -> None:
        settings = get_settings()
        self.base_url = (base_url or settings.n8n_url).rstrip("/")
        self.api_key = api_key if api_key is not None else settings.get_n8n_api_key_str()
        self.timeout = timeout or settings.n8n_timeout_seconds
        self.verify_ssl = verify_ssl if verify_ssl is not None else settings.n8n_verify_ssl

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

    def check_connectivity(self) -> bool:
        """Verify network connectivity to n8n instance."""
        try:
            with httpx.Client(timeout=self.timeout, verify=self.verify_ssl) as client:
                resp = client.get(self.base_url)
                return resp.status_code in (200, 301, 302)
        except Exception as e:
            logger.warning("n8n connectivity check failed: %s", type(e).__name__)
            return False

    def get_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """Fetch workflow by ID."""
        url = f"{self.base_url}/api/v1/workflows/{workflow_id}"
        try:
            with httpx.Client(timeout=self.timeout, verify=self.verify_ssl) as client:
                resp = client.get(url, headers=self._get_headers())
                if resp.status_code == 404:
                    raise ProviderError(f"Workflow {workflow_id} not found")
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPStatusError as e:
            raise ProviderError(f"n8n API error: HTTP {e.response.status_code}") from e
        except Exception as e:
            raise ProviderError(f"Failed to fetch workflow: {type(e).__name__}") from e

    def trigger_webhook(
        self,
        webhook_path: str,
        payload: Optional[Dict[str, Any]] = None,
        method: str = "POST",
    ) -> Dict[str, Any]:
        """
        Trigger an n8n webhook (Workaround N8N-WA-001).
        """
        clean_path = webhook_path.lstrip("/")
        url = f"{self.base_url}/webhook/{clean_path}"
        try:
            with httpx.Client(timeout=self.timeout, verify=self.verify_ssl) as client:
                if method.upper() == "GET":
                    resp = client.get(url, params=payload, headers=self._get_headers())
                else:
                    resp = client.post(url, json=payload or {}, headers=self._get_headers())
                resp.raise_for_status()
                try:
                    return resp.json()
                except Exception:
                    return {"status": "triggered", "response_text": resp.text}
        except httpx.HTTPStatusError as e:
            raise ProviderError(f"Webhook execution failed: HTTP {e.response.status_code}") from e
        except Exception as e:
            raise ProviderError(f"Webhook execution error: {type(e).__name__}") from e
