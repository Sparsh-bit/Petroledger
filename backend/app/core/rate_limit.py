"""PetroLedger — Shared Limiter instance.

Defined here (not in `app.main`) so route modules can import the
`limiter` without a circular dependency on the FastAPI app.
"""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import get_settings

_settings = get_settings()

limiter: Limiter = Limiter(
    key_func=get_remote_address,
    storage_uri="memory://" if (_settings.is_development or _settings.ENVIRONMENT == "test") else _settings.REDIS_URL,
    default_limits=["200/minute"],
    enabled=(_settings.ENVIRONMENT != "test"),
)
