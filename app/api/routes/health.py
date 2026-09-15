"""Health and readiness probe endpoints."""

import logging
from fastapi import APIRouter, Response, status
from app.core.config import get_settings
from app.db.session import check_database_connection
from app.providers.n8n.client import N8nClient

logger = logging.getLogger(__name__)

router = APIRouter(tags=["System"])


@router.get("/health", status_code=status.HTTP_200_OK)
def get_health() -> dict:
    """
    Liveness probe indicating the application process is running.
    Never exposes secrets or credentials.
    """
    settings = get_settings()
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
    }


@router.get("/ready")
def get_readiness(response: Response) -> dict:
    """
    Readiness probe verifying external dependencies (database and n8n).
    If a required dependency is unreachable, reports 'degraded' status and HTTP 503.
    Never exposes sensitive credentials or connection passwords.
    """
    settings = get_settings()

    # 1. Check database connectivity
    db_connected, db_status = check_database_connection()

    # 2. Check n8n provider reachability
    n8n_client = N8nClient()
    n8n_connected = n8n_client.check_connectivity()
    n8n_status = "connected" if n8n_connected else "unreachable"

    all_ready = db_connected and n8n_connected

    if not all_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "ready" if all_ready else "degraded",
        "app_version": settings.app_version,
        "components": {
            "database": {
                "status": "connected" if db_connected else "unreachable",
                "details": db_status,
            },
            "n8n": {
                "status": n8n_status,
            },
        },
    }
