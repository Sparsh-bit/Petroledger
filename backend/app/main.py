"""
PetroLedger — FastAPI Application Entry Point.

Configures middleware, exception handlers, lifespan events,
and mounts the v1 API router.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import text

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.rate_limit import limiter
from app.core.exceptions import PetroLedgerError
from app.core.logging import RequestLoggingMiddleware, configure_logging
from app.db.session import engine

settings = get_settings()
configure_logging(settings.ENVIRONMENT)
logger = structlog.stdlib.get_logger("petroledger")


# ── Enum Validation ─────────────────────────────────────────────────────

async def _validate_db_enums() -> None:
    """Compare Python enum values against PostgreSQL pg_enum at startup.
    Logs a WARNING for every mismatch so bugs are caught before they hit prod.
    """
    from app.models.assignments import AnomalyFlagType, AnomalySeverity
    from app.models.fms import (
        FleetEntryMethod,
        FleetProvider,
        FmsTxnStatus,
        PosEntryMethod,
    )
    from app.models.organization import OmcType
    from app.models.pump import FuelProductCode, FuelType
    from app.models.reconciliation import ReconciliationStatus, VarianceType
    from app.models.shift import ShiftSlot, ShiftStatus
    from app.models.transaction import UpiMatchStatus
    from app.models.user import UserRole

    python_enums: dict[str, set[str]] = {
        "user_role": {e.value for e in UserRole},
        "fuel_type": {e.value for e in FuelType},
        "shift_status": {e.value for e in ShiftStatus},
        "shift_slot": {e.value for e in ShiftSlot},
        "reconciliation_status": {e.value for e in ReconciliationStatus},
        "recon_variance_type": {e.value for e in VarianceType},
        "omc_type": {e.value for e in OmcType},
        "fuel_product_code": {e.value for e in FuelProductCode},
        "upi_match_status": {e.value for e in UpiMatchStatus},
        "fms_txn_status": {e.value for e in FmsTxnStatus},
        "pos_entry_method": {e.value for e in PosEntryMethod},
        "fleet_provider": {e.value for e in FleetProvider},
        "fleet_entry_method": {e.value for e in FleetEntryMethod},
        "anomaly_severity": {e.value for e in AnomalySeverity},
        "anomaly_flag_type": {e.value for e in AnomalyFlagType},
    }

    async with engine.connect() as conn:
        rows = await conn.execute(text(
            "SELECT t.typname, e.enumlabel "
            "FROM pg_type t JOIN pg_enum e ON e.enumtypid = t.oid "
            "ORDER BY t.typname, e.enumsortorder"
        ))
        db_enums: dict[str, set[str]] = {}
        for typname, enumlabel in rows:
            db_enums.setdefault(typname, set()).add(enumlabel)

    all_ok = True
    for name, py_values in python_enums.items():
        if name not in db_enums:
            logger.warning("Enum mismatch: '%s' exists in Python but NOT in DB", name)
            all_ok = False
            continue
        db_values = db_enums[name]
        missing_in_db = py_values - db_values
        missing_in_py = db_values - py_values
        if missing_in_db:
            logger.warning("Enum '%s': values in Python but missing in DB: %s", name, missing_in_db)
            all_ok = False
        if missing_in_py:
            logger.warning("Enum '%s': values in DB but missing in Python: %s", name, missing_in_py)
            all_ok = False

    if all_ok:
        logger.info("Enum validation passed — all %d enums match DB", len(python_enums))


# ── Lifespan ────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup / shutdown lifecycle hook."""
    # ── Startup ─────────────────────────────────────────────────────
    logger.info(
        "Starting PetroLedger v%s [%s]",
        settings.APP_VERSION,
        settings.ENVIRONMENT,
    )

    # ── Verify database connectivity ──────────────────────────────────
    # Non-fatal in dev (log + continue); fatal in prod (log + re-raise so
    # the platform orchestrator restarts with a visible error).
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("Database connection verified")
    except Exception as exc:  # noqa: BLE001
        if settings.is_production:
            logger.error(
                "Database connection check failed at startup (prod): %s",
                exc,
                exc_info=True,
            )
            raise
        logger.warning(
            "Database connection check failed at startup (dev — continuing): %s",
            exc,
        )

    # ── Validate Python enums match PostgreSQL enums ──────────────────
    # PostgreSQL-only. Skipped gracefully on SQLite/other backends and on
    # transient connection failures. Logs warnings on mismatch; never raises.
    if "postgresql" in settings.DATABASE_URL:
        try:
            await _validate_db_enums()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Enum validation skipped: %s", exc)

    # Run Alembic migrations on boot so prod DB schema is always current.
    # Idempotent: no-op when already at head.
    try:
        import asyncio as _asyncio
        from alembic import command
        from alembic.config import Config as _AlembicConfig

        def _run_migrations() -> None:
            cfg = _AlembicConfig("alembic.ini")
            command.upgrade(cfg, "head")

        await _asyncio.to_thread(_run_migrations)
        logger.info("Alembic migrations applied ✓")
    except Exception as exc:  # noqa: BLE001
        logger.error("Alembic migration failed: %s", exc, exc_info=True)

    # Idempotent superadmin seed — runs on every boot, no-op if user exists.
    if settings.SUPERADMIN_EMAIL and settings.SUPERADMIN_PASSWORD:
        try:
            from scripts.seed_superadmin import seed as _seed_superadmin
            await _seed_superadmin()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Superadmin seed skipped: %s", exc)

    yield  # ← application runs here

    # ── Shutdown ────────────────────────────────────────────────────
    logger.info("Shutting down PetroLedger …")
    await engine.dispose()
    logger.info("Database connections closed ✓")


# ── App Instance ────────────────────────────────────────────────────────

app = FastAPI(
    title="PetroLedger",
    version=settings.APP_VERSION,
    description="Multi-tenant petrol pump reconciliation SaaS API",
    lifespan=lifespan,
    docs_url="/docs" if settings.show_docs else None,
    redoc_url="/redoc" if settings.show_docs else None,
    openapi_url="/openapi.json" if settings.show_docs else None,
)


# ── Middleware ──────────────────────────────────────────────────────────

# Rate limiting — register limiter on app.state + add exception handler + middleware.
# Individual routes declare their own limits with `@limiter.limit("10/minute")`.
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Uniform rate-limit 429 response."""
    retry_after = getattr(exc, "retry_after", None) or 60
    return JSONResponse(
        status_code=429,
        headers={"Retry-After": str(retry_after)},
        content={
            "error": "RateLimitExceeded",
            "message": "Too many requests. Please slow down.",
            "retry_after": retry_after,
        },
    )


# Middleware is applied in reverse-add order (last added = outermost).
# CORS must be outermost so it adds Access-Control-Allow-Origin to every
# response, including error responses returned by inner middleware.
@app.middleware("http")
async def tenant_lock_middleware(request: Request, call_next):
    """Reject requests for tenants with is_locked=True (except auth/provider/health).

    SUPERADMIN/PROVIDER bearer tokens bypass the lock. The locked flag is
    cached in Redis (key ``tenant_locked:{tenant_id}``, TTL 60s) to avoid a
    DB hit on every request; cache failures fall back to a DB query.
    """
    path = request.url.path
    # Public/bypass prefixes — auth endpoints, provider portal, health, docs.
    bypass_prefixes = (
        "/api/v1/auth/",
        "/api/v1/provider/",
        "/health",
        "/docs",
        "/redoc",
        "/openapi.json",
    )
    if any(path.startswith(p) for p in bypass_prefixes):
        return await call_next(request)

    auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
    if not auth_header or not auth_header.lower().startswith("bearer "):
        return await call_next(request)

    token = auth_header.split(" ", 1)[1].strip()
    try:
        from jose import JWTError

        from app.core.security import decode_token
        from app.core.tenant_lock_cache import is_tenant_locked
        from app.models.user import UserRole

        try:
            payload = decode_token(token)
        except JWTError:
            return await call_next(request)

        role = payload.get("role")
        if role in (UserRole.SUPERADMIN.value, UserRole.PROVIDER.value):
            return await call_next(request)

        tenant_id = payload.get("tenant_id")
        if not tenant_id:
            return await call_next(request)

        if await is_tenant_locked(str(tenant_id)):
            return JSONResponse(
                status_code=423,
                content={
                    "error": "TenantLocked",
                    "message": "Account locked — please contact support.",
                },
            )
    except Exception:
        # Never block a request because of a middleware glitch.
        pass
    return await call_next(request)


app.add_middleware(SlowAPIMiddleware)
app.add_middleware(RequestLoggingMiddleware)

# Security headers — inside CORS, outside everything else.
from app.core.security_headers import SecurityHeadersMiddleware  # noqa: E402
app.add_middleware(SecurityHeadersMiddleware)

# Prometheus metrics — optional. Exposes /metrics when the dep is installed.
try:
    from prometheus_fastapi_instrumentator import Instrumentator

    Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)
except Exception:
    logger.info("prometheus-fastapi-instrumentator not installed — /metrics disabled")
# CORS_ORIGINS may be ["*"] (dev/any) or an explicit whitelist (prod).
_cors_origins = settings.CORS_ORIGINS
_allow_all = len(_cors_origins) == 1 and _cors_origins[0] == "*"
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if _allow_all else _cors_origins,
    allow_credentials=not _allow_all,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


# ── Global Exception Handlers ──────────────────────────────────────────


@app.exception_handler(PetroLedgerError)
async def petroledger_exception_handler(
    request: Request,
    exc: PetroLedgerError,
) -> JSONResponse:
    """Handle all custom PetroLedger exceptions uniformly."""
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict(),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """Catch-all for unexpected errors — log and return 500."""
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "error": "InternalServerError",
            "message": "An unexpected error occurred."
            if settings.is_production
            else str(exc),
        },
    )


# ── Root & Health ──────────────────────────────────────────────────────


@app.get("/", include_in_schema=False)
@app.head("/", include_in_schema=False)
async def root():
    """Service info. Also answers uptime probes (GET/HEAD /)."""
    return {
        "service": "petroledger-api",
        "version": settings.APP_VERSION,
        "status": "ok",
        "docs": "/docs" if settings.show_docs else None,
    }


@app.get("/health")
@app.head("/health", include_in_schema=False)
async def health_check():
    """Liveness probe used by Render and load balancers."""
    return {
        "status": "healthy",
        "environment": settings.ENVIRONMENT,
        "version": settings.APP_VERSION,
    }

# ── Mount API Router ───────────────────────────────────────────────────

app.include_router(api_router, prefix="/api/v1")
