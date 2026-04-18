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
    storage_uri=_settings.REDIS_URL if not _settings.is_development else "memory://",
    default_limits=["200/minute"],
)
