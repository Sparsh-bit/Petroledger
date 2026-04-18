"""PetroLedger — FastAPI Authentication Dependencies."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError
from app.core.security import decode_token
from app.db.session import get_db
from app.models.user import User
from app.utils.token_blacklist import is_blacklisted

bearer_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Decode the JWT from the Authorization header and return the User."""
    raw_token = credentials.credentials

    # Reject tokens that have been explicitly invalidated via logout
    if is_blacklisted(raw_token):
        raise AuthenticationError("Token has been revoked. Please log in again.")

    try:
        payload = decode_token(raw_token)
    except JWTError as err:
        raise AuthenticationError("Invalid or expired token") from err

    if payload.get("type") != "access":
        raise AuthenticationError("Invalid token type")

    user_id: str | None = payload.get("sub")
    if user_id is None:
        raise AuthenticationError("Invalid token payload")

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()

    if user is None:
        raise AuthenticationError("User not found")

    # Verify tenant_id in token still matches DB (guards against tenant reassignment)
    token_tenant_id: str | None = payload.get("tenant_id")
    if token_tenant_id and str(user.tenant_id) != token_tenant_id:
        raise AuthenticationError("Token tenant mismatch — please log in again")

    # Reject tokens issued before a password reset / global invalidation.
    if user.tokens_invalidated_at is not None:
        iat_claim = payload.get("iat")
        if iat_claim is not None:
            issued_at = datetime.fromtimestamp(int(iat_claim), tz=UTC)
            if issued_at < user.tokens_invalidated_at:
                raise AuthenticationError(
                    "Token invalidated. Please log in again."
                )

    return user


async def get_current_active_user(
    user: User = Depends(get_current_user),
) -> User:
    """Ensure the current user account is active."""
    if not user.is_active:
        raise AuthenticationError("Account is deactivated")
    return user
