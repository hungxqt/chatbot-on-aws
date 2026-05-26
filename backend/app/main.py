"""FastAPI application entry point."""

import asyncio
import contextlib
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import TypedDict

from fastapi import FastAPI
from fastapi_pagination import add_pagination

from app.api.exception_handlers import register_exception_handlers
from app.api.router import api_router
from app.clients.redis import RedisClient
from app.core.cloudwatch_metrics import (
    BackendErrorRateMiddleware,
    backend_error_rate_collector,
    run_cloudwatch_metrics_publisher,
)
from app.core.config import settings
from app.core.logfire_setup import instrument_app, setup_logfire
from app.core.logging import setup_logging
from app.core.middleware import RequestIDMiddleware
from app.rag.bedrock_kb import BedrockKBClient

logger = logging.getLogger(__name__)


class LifespanState(TypedDict, total=False):
    """Lifespan state - resources available via request.state."""

    redis: RedisClient
    kb_client: BedrockKBClient


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[LifespanState, None]:
    """Application lifespan - startup and shutdown events.

    Resources yielded here are available via request.state in route handlers.
    See: https://asgi.readthedocs.io/en/latest/specs/lifespan.html#lifespan-state
    """
    # === Startup ===
    state: LifespanState = {}
    setup_logfire()
    from app.core.logfire_setup import instrument_asyncpg

    instrument_asyncpg()
    from app.core.logfire_setup import instrument_redis

    instrument_redis()
    from app.core.logfire_setup import instrument_httpx

    instrument_httpx()
    from app.core.logfire_setup import instrument_pydantic_ai

    instrument_pydantic_ai()
    if settings.REDIS_ENABLED:
        redis_client = RedisClient()
        await redis_client.connect()
        state["redis"] = redis_client
        from app.core.cache import setup_cache

        setup_cache(redis_client)
    else:
        logger.info("Redis disabled (REDIS_ENABLED=false)")

    try:
        kb_client = BedrockKBClient.from_settings()
        state["kb_client"] = kb_client
        logger.info("Bedrock KB client initialized")
    except Exception as e:
        logger.error(f"Bedrock KB client init failed: {e}. RAG will not be available.")

    cloudwatch_metrics_task: asyncio.Task[None] | None = None
    if settings.CLOUDWATCH_METRICS_ENABLED:
        cloudwatch_metrics_task = asyncio.create_task(run_cloudwatch_metrics_publisher())

    yield state

    # === Shutdown ===
    if cloudwatch_metrics_task:
        cloudwatch_metrics_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await cloudwatch_metrics_task

    if "redis" in state:
        await state["redis"].close()
    from app.db.session import close_db

    await close_db()


# Environments where API docs should be visible
SHOW_DOCS_ENVIRONMENTS = ("local", "staging", "development")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    # Only show docs in allowed environments (hide in production)
    show_docs = settings.ENVIRONMENT in SHOW_DOCS_ENVIRONMENTS
    openapi_url = f"{settings.API_V1_STR}/openapi.json" if show_docs else None
    docs_url = "/docs" if show_docs else None
    redoc_url = "/redoc" if show_docs else None

    # OpenAPI tags for better documentation organization
    openapi_tags = [
        {
            "name": "health",
            "description": "Health check endpoints for monitoring and Kubernetes probes",
        },
        {
            "name": "auth",
            "description": "Authentication endpoints - login, register, token refresh",
        },
        {
            "name": "users",
            "description": "User management endpoints",
        },
        {
            "name": "sessions",
            "description": "Session management - view and manage active login sessions",
        },
        {
            "name": "conversations",
            "description": "AI conversation persistence - manage chat history",
        },
        {
            "name": "agent",
            "description": "AI agent WebSocket endpoint for real-time chat",
        },
        {
            "name": "rag",
            "description": "Retrieval Augmented Generation endpoints",
        },
    ]

    # PII redaction in logs (GDPR/compliance)
    setup_logging()

    app = FastAPI(
        title=settings.PROJECT_NAME,
        summary="FastAPI application with Logfire observability",
        description="""
My FastAPI project

## Features
- **Authentication**: JWT-based authentication with refresh tokens
- **API Key**: Header-based API key authentication
- **Database**: Async database operations
- **Redis**: Caching and session storage
- **Rate Limiting**: Request rate limiting per client
- **AI Agent**: PydanticAI-powered conversational assistant
- **Observability**: Logfire integration for tracing and monitoring
- **RAG**: Retrieval Augmented Generation with Milvus and LangChain

## Documentation

- [Swagger UI](/docs) - Interactive API documentation
- [ReDoc](/redoc) - Alternative documentation view
        """.strip(),
        version="0.1.0",
        openapi_url=openapi_url,
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_tags=openapi_tags,
        contact={
            "name": "Your Name",
            "email": "your@email.com",
        },
        license_info={
            "name": "MIT",
            "identifier": "MIT",
        },
        lifespan=lifespan,
    )
    # Logfire instrumentation
    instrument_app(app)

    # Request ID middleware (for request correlation/debugging)
    app.add_middleware(RequestIDMiddleware)

    if settings.CLOUDWATCH_METRICS_ENABLED:
        app.add_middleware(
            BackendErrorRateMiddleware,
            collector=backend_error_rate_collector,
        )

    # Exception handlers
    register_exception_handlers(app)

    # CORS middleware
    from starlette.middleware.cors import CORSMiddleware

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
        allow_methods=settings.CORS_ALLOW_METHODS,
        allow_headers=settings.CORS_ALLOW_HEADERS,
    )

    # Sentry
    if settings.SENTRY_DSN:
        import sentry_sdk

        sentry_sdk.init(dsn=settings.SENTRY_DSN, enable_tracing=True)

    # Prometheus metrics
    import sys
    from prometheus_client import CollectorRegistry
    from prometheus_fastapi_instrumentator import Instrumentator

    registry = CollectorRegistry() if "pytest" in sys.modules else None

    instrumentator = Instrumentator(
        should_group_status_codes=True,
        should_ignore_untemplated=True,
        should_respect_env_var=False,
        should_instrument_requests_inprogress=True,
        excluded_handlers=[
            "/health",
            "/health/ready",
            "/health/live",
            settings.PROMETHEUS_METRICS_PATH,
        ],
        inprogress_name="http_requests_inprogress",
        inprogress_labels=True,
        registry=registry,
    )
    instrumentator.instrument(app).expose(
        app,
        endpoint=settings.PROMETHEUS_METRICS_PATH,
        include_in_schema=settings.PROMETHEUS_INCLUDE_IN_SCHEMA,
    )

    # Rate limiting
    # Note: slowapi requires app.state.limiter - this is a library requirement,
    # not suitable for lifespan state pattern which is for request-scoped access
    from slowapi import _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded

    from app.core.rate_limit import limiter

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # Session middleware (for admin authentication and/or OAuth)
    from starlette.middleware.sessions import SessionMiddleware

    app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)

    # Admin panel (environment restricted)
    ADMIN_ALLOWED_ENVIRONMENTS = ["development", "local", "staging"]

    if settings.ENVIRONMENT in ADMIN_ALLOWED_ENVIRONMENTS:
        from app.admin import setup_admin

        setup_admin(app)

    # API Version Deprecation (uncomment when deprecating old versions)
    # Example: Mark v1 as deprecated when v2 is ready
    # from app.api.versioning import VersionDeprecationMiddleware
    # app.add_middleware(
    #     VersionDeprecationMiddleware,
    #     deprecated_versions={
    #         "v1": {
    #             "sunset": "2025-12-31",
    #             "link": "/docs/migration/v2",
    #             "message": "Please migrate to API v2",
    #         }
    #     },
    # )

    # Include API router
    app.include_router(api_router, prefix=settings.API_V1_STR)

    # Pagination
    add_pagination(app)

    return app


app = create_app()
