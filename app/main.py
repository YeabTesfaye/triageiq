import time
import uuid

import structlog
from app.config import get_settings
from app.infrastructure.redis_client import get_redis
from app.presentation.routers import admin, analytics, auth, ticket
from app.presentation.routers.chat_router import router as chat_router
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

# ── Structured Logging Setup ───────────────────────────────────────────────────
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(20),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)
log = structlog.get_logger(__name__)

# ── Rate Limiter ───────────────────────────────────────────────────────────────
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["100/minute"],
)


# ── Properly typed rate limit handler ──────────────────────────────────────────
async def rate_limit_handler(request: Request, exc: Exception) -> Response:
    return await _rate_limit_exceeded_handler(request, exc)  # type: ignore


# ── Lifespan ───────────────────────────────────────────────────────────────────


# ── App Factory ────────────────────────────────────────────────────────────────
def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="TriageIQ",
        description=(
            "Production-grade AI support ticket triage system. "
            "All protected endpoints require Bearer JWT authentication."
        ),
        version=settings.APP_VERSION,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        swagger_ui_parameters={"persistAuthorization": True},
    )

    # ── OpenAPI Security ───────────────────────────────────────────────────────
    from fastapi.openapi.utils import get_openapi

    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
        )
        schema["components"]["securitySchemes"] = {
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
            }
        }
        for path in schema["paths"].values():
            for operation in path.values():
                operation.setdefault("security", [{"BearerAuth": []}])
        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi  # type: ignore

    # ── CORS ───────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )

    # ── Rate Limiting ──────────────────────────────────────────────────────────
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_handler)  # type: ignore[arg-type]
    app.add_middleware(SlowAPIMiddleware)

    # ── Request Context Middleware ─────────────────────────────────────────────
    @app.middleware("http")
    async def request_context_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        start_time = time.perf_counter()
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            client_ip=request.client.host if request.client else "unknown",
        )
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start_time) * 1000
        response.headers["X-Request-ID"] = request_id
        log.info(
            "request_complete",
            status_code=response.status_code,
            duration_ms=round(duration_ms, 2),
        )
        return response

    # ── Security Headers ───────────────────────────────────────────────────────
    @app.middleware("http")
    async def security_headers_middleware(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if settings.ENV == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    # ── Metrics ────────────────────────────────────────────────────────────────
    if settings.ENABLE_METRICS:
        Instrumentator(
            should_group_status_codes=False,
            should_ignore_untemplated=True,
            should_respect_env_var=False,
            excluded_handlers=["/health", "/metrics"],
        ).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

    # ── Routers ────────────────────────────────────────────────────────────────
    api_prefix = "/api/v1"
    app.include_router(auth.router, prefix=api_prefix)
    app.include_router(ticket.router, prefix=api_prefix)
    app.include_router(admin.router, prefix=api_prefix)
    app.include_router(analytics.router, prefix=api_prefix)
    app.include_router(chat_router, prefix=api_prefix)

    print(chat_router, "Chat router")

    # ── Health ─────────────────────────────────────────────────────────────────
    @app.get("/health", include_in_schema=False)
    async def health():
        return {"status": "ok", "version": settings.APP_VERSION}

    @app.get("/readiness", include_in_schema=False)
    async def readiness():
        checks = {}
        try:
            from app.infrastructure.database import get_engine

            async with get_engine().connect() as conn:
                await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
            checks["database"] = "ok"
        except Exception as e:
            log.error("readiness_db_failed", error=str(e))
            checks["database"] = "error"
        try:
            redis = await get_redis()
            result = redis.ping()
            if hasattr(result, "__await__"):
                await result
            checks["redis"] = "ok"
        except Exception as e:
            log.error("readiness_redis_failed", error=str(e))
            checks["redis"] = "error"
        all_ok = all(v == "ok" for v in checks.values())
        return JSONResponse(
            status_code=(status.HTTP_200_OK if all_ok else status.HTTP_503_SERVICE_UNAVAILABLE),
            content={
                "status": "ok" if all_ok else "degraded",
                "checks": checks,
            },
        )

    return app


app = create_app()
