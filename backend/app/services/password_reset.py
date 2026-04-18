"""PetroLedger — Password reset service.

request(email) → generate a cryptographically-random token, store its
bcrypt hash + 24h expiry, email the raw token as a link.

confirm(token, new_password) → find the user with a matching token hash
whose expiry hasn't passed, enforce password complexity, rotate the
hash, clear the token, bump `tokens_invalidated_at` so every JWT issued
before the reset (including stolen refresh tokens) is rejected.
"""

from __future__ import annotations

import asyncio
import re
import secrets
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.email import send_password_reset_email
from app.core.exceptions import ValidationError
from app.core.security import hash_password, verify_password
from app.models.user import User

log = structlog.stdlib.get_logger("petroledger.services.password_reset")

_TOKEN_TTL_HOURS = 24
_PASSWORD_RULES = [
    (r".{8,}", "at least 8 characters"),
    (r"[A-Z]", "at least one uppercase letter"),
    (r"\d", "at least one digit"),
    (r"[^A-Za-z0-9]", "at least one special character"),
]


def _validate_password_strength(password: str) -> None:
    """Raise ValidationError if the password fails any complexity rule."""
    if len(password) > 128:
        raise ValidationError(message="Password must be 128 characters or less.")
    failures = [rule for pattern, rule in _PASSWORD_RULES if not re.search(pattern, password)]
    if failures:
        raise ValidationError(
            message="Password must contain " + ", ".join(failures) + "."
        )


class PasswordResetService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def request(self, email: str) -> None:
        """Generate and email a reset token. Silently succeeds if email unknown."""
        settings = get_settings()

        result = await self.db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user is None or not user.is_active:
            log.info("password_reset_request_unknown_or_inactive", email=email)
            return

        raw_token = secrets.token_urlsafe(32)
        user.reset_token_hash = hash_password(raw_token)
        user.reset_token_expires_at = datetime.now(UTC) + timedelta(
            hours=_TOKEN_TTL_HOURS
        )
        await self.db.flush()

        reset_url = f"{settings.FRONTEND_OWNER_URL}/reset-password?token={raw_token}"
        await asyncio.to_thread(
            send_password_reset_email,
            to_email=user.email,
            full_name=user.email.split("@")[0],
            reset_url=reset_url,
        )
        log.info("password_reset_requested", user_id=str(user.id))

    async def confirm(self, token: str, new_password: str) -> None:
        """Validate token + strength, rotate password, invalidate all prior JWTs."""
        _validate_password_strength(new_password)

        now = datetime.now(UTC)
        # Scan only users with an active, non-expired token — small working set.
        result = await self.db.execute(
            select(User).where(
                User.reset_token_hash.is_not(None),
                User.reset_token_expires_at > now,
            )
        )
        candidates = result.scalars().all()

        match: User | None = None
        for user in candidates:
            if user.reset_token_hash and verify_password(token, user.reset_token_hash):
                match = user
                break

        if match is None:
            raise ValidationError(
                message="Reset link is invalid or has expired. Please request a new one."
            )

        match.hashed_password = hash_password(new_password)
        match.reset_token_hash = None
        match.reset_token_expires_at = None
        match.tokens_invalidated_at = now
        await self.db.flush()
        log.info("password_reset_confirmed", user_id=str(match.id))
