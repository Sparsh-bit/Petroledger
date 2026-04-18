"""
PetroLedger — JWT Token Blacklist (Redis-backed).

On logout the access token's JTI (or its SHA-256 hash if no JTI is
present) is stored in Redis with a TTL equal to the token's remaining
lifetime.  Every authenticated request checks the blacklist before
allowing access.

Keys: ``petroledger:blacklist:{token_hash}``
Value: ``"1"``
TTL: seconds until the token naturally expires
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import redis as redis_lib
import structlog

from app.core.config import get_settings

log = structlog.stdlib.get_logger("petroledger.utils.token_blacklist")
settings = get_settings()

_redis = redis_lib.Redis.from_url(
    settings.REDIS_URL,
    decode_responses=True,
    socket_connect_timeout=0.5,   # fail fast when Redis is not running
    socket_timeout=0.5,
    retry_on_timeout=False,
)
_KEY_PREFIX = "petroledger:blacklist:"


def _token_key(token: str) -> str:
    """Derive a stable, short Redis key from a raw JWT string."""
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return f"{_KEY_PREFIX}{digest}"


def blacklist_token(token: str, exp: int) -> None:
    """Add *token* to the Redis blacklist.

    Parameters
    ----------
    token:
        The raw JWT string to blacklist.
    exp:
        Unix timestamp (seconds) at which the token expires.
        The Redis TTL is set to ``exp - now``.  If the token is already
        expired this is a no-op.
    """
    now = int(datetime.now(UTC).timestamp())
    ttl = exp - now
    if ttl <= 0:
        # Token already expired — no need to blacklist
        return

    key = _token_key(token)
    try:
        _redis.setex(key, ttl, "1")
        log.info("token_blacklisted", ttl_seconds=ttl)
    except redis_lib.RedisError as exc:
        # Blacklisting is best-effort.  Log but don't block the logout response.
        log.warning("token_blacklist_failed", error=str(exc))


def is_blacklisted(token: str) -> bool:
    """Return ``True`` when *token* has been blacklisted (i.e. logged out).

    Falls back to ``False`` on Redis errors so auth remains functional
    even when Redis is temporarily unavailable.
    """
    key = _token_key(token)
    try:
        return bool(_redis.exists(key))
    except redis_lib.RedisError as exc:
        log.warning("token_blacklist_check_failed", error=str(exc))
        return False
