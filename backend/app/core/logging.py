"""
PetroLedger — Structured Logging Configuration.

Uses ``structlog`` for structured, contextual logging.
- **Dev**: pretty, colored console output.
- **Prod**: JSON lines for log aggregators.

Every log entry carries a ``request_id`` drawn from a :mod:`contextvars`
context variable that the :class:`RequestLoggingMiddleware` sets per-request.
"""

from __future__ import annotations

import logging
import sys
import time
import uuid
from contextvars import ContextVar

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

# ── Context Variable ────────────────────────────────────────────────────

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")


# ── Structlog Processors ───────────────────────────────────────────────


def _add_request_id(
    logger: logging.Logger,
    method_name: str,
    event_dict: dict,
) -> dict:
    """Inject the current ``request_id`` into every log entry."""
    rid = request_id_ctx.get("")
    if rid:
        event_dict["request_id"] = rid
    return event_dict


# ── Public API ──────────────────────────────────────────────────────────


def configure_logging(environment: str) -> None:
    """
    Bootstrap structlog + stdlib logging for the given environment.

    Parameters
    ----------
    environment:
        One of ``"dev"``, ``"staging"``, ``"prod"``.
    """
    is_prod = environment == "prod"

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
        _add_request_id,
    ]

    if is_prod:
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    root_logger = logging.getLogger()
    root_logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.DEBUG if not is_prod else logging.INFO)

    # Quieten noisy third-party loggers
    for name in ("uvicorn.access", "sqlalchemy.engine", "httpcore", "httpx"):
        logging.getLogger(name).setLevel(logging.WARNING)


# ── FastAPI Middleware ──────────────────────────────────────────────────


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    ASGI middleware that:

    1. Generates a unique ``request_id`` and stores it in :data:`request_id_ctx`.
    2. Logs every request with method, path, status_code, duration_ms, and request_id.
    3. Adds ``X-Request-ID`` to the response headers.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        from starlette.responses import JSONResponse

        rid = request.headers.get("X-Request-ID", uuid.uuid4().hex)
        request_id_ctx.set(rid)

        logger = structlog.stdlib.get_logger("petroledger.request")
        start = time.perf_counter()

        try:
            response = await call_next(request)
        except BaseException as exc:
            elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
            logger.exception(
                "unhandled_exception",
                method=request.method,
                path=request.url.path,
                duration_ms=elapsed_ms,
                request_id=rid,
            )
            from app.core.config import get_settings as _get_settings
            _settings = _get_settings()
            exc_str = str(exc)
            message = (
                f"{type(exc).__name__}" + (f": {exc_str}" if exc_str else "")
                if not _settings.is_production
                else "An unexpected error occurred."
            )
            return JSONResponse(
                status_code=500,
                content={"error": "InternalServerError", "message": message},
                headers={"X-Request-ID": rid},
            )

        elapsed_ms = round((time.perf_counter() - start) * 1000, 1)

        log_level = (
            "error" if response.status_code >= 500
            else "warning" if response.status_code >= 400
            else "info"
        )
        getattr(logger, log_level)(
            "request_handled",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=elapsed_ms,
            request_id=rid,
        )

        response.headers["X-Request-ID"] = rid
        return response
