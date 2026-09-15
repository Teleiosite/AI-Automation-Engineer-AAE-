"""AAE FastAPI Application Entry Point."""

import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.api.routes.health import router as health_router
from app.core.config import get_settings
from app.core.logging import correlation_id_ctx, setup_logging
import logging

logger = logging.getLogger("aae.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Structured application lifespan manager."""
    settings = get_settings()
    setup_logging(log_level=settings.log_level, log_format=settings.log_format)
    logger.info("Starting %s v%s in %s mode", settings.app_name, settings.app_version, settings.environment)
    yield
    logger.info("Shutting down %s", settings.app_name)


def create_app() -> FastAPI:
    """Application factory for AAE."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="AI Automation Engineer - Autonomous Automation Platform",
        lifespan=lifespan,
        docs_url="/docs" if settings.debug or settings.environment != "production" else None,
        redoc_url="/redoc" if settings.debug or settings.environment != "production" else None,
    )

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.environment == "development" else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Security Headers Middleware
    @app.middleware("http")
    async def security_headers_middleware(request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        if settings.environment == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    # Rate Limiting Middleware
    from app.core.security import RateLimiter
    api_rate_limiter = RateLimiter(max_requests=120, window_seconds=60.0)

    @app.middleware("http")
    async def rate_limiting_middleware(request: Request, call_next) -> Response:
        client_ip = request.client.host if request.client else "unknown"
        if not api_rate_limiter.is_allowed(client_ip):
            return JSONResponse(
                status_code=429,
                content={"error": "Too Many Requests", "message": "Rate limit exceeded. Try again later."},
            )
        return await call_next(request)

    # Correlation ID Middleware
    @app.middleware("http")
    async def correlation_id_middleware(request: Request, call_next) -> Response:
        cid = request.headers.get("X-Request-ID") or request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
        token = correlation_id_ctx.set(cid)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = cid
            return response
        finally:
            correlation_id_ctx.reset(token)

    # Global Exception Handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error("Unhandled exception: %s", type(exc).__name__, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal Server Error",
                "message": "An unexpected server error occurred.",
                "correlation_id": correlation_id_ctx.get(),
            },
        )

    # Mount Routes
    app.include_router(health_router)

    return app


app = create_app()
