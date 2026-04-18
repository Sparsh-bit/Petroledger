"""PetroLedger — SMS OTP service (AWS SNS).

Generates a cryptographically-random 6-digit OTP, stores its bcrypt
hash on the user record with a 10-minute expiry, and sends the raw
code to the user's phone via AWS SNS Publish.

Rate-limited (3 requests per phone per 15 min) via Redis.
"""

from __future__ import annotations

import asyncio
import re
import secrets
from datetime import UTC, datetime, timedelta

import boto3
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError, ValidationError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.schemas.user import LoginResponse, UserResponse
from app.utils.token_blacklist import _redis  # reuse the shared Redis client

log = structlog.stdlib.get_logger("petroledger.services.otp")

_OTP_TTL_MINUTES = 10
_OTP_LENGTH = 6
_RATE_LIMIT_WINDOW_SEC = 15 * 60
_RATE_LIMIT_MAX = 3
_INDIAN_MOBILE_RE = re.compile(r"^\+91[6-9]\d{9}$")


def _rate_limit_key(phone: str) -> str:
    return f"petroledger:otp_rate:{phone}"


def _validate_phone(phone: str) -> None:
    if not _INDIAN_MOBILE_RE.match(phone):
        raise ValidationError(
            message="Invalid phone number. Use E.164 format: +91XXXXXXXXXX"
        )


def _generate_otp() -> str:
    """Cryptographically-random 6-digit code."""
    return f"{secrets.randbelow(10**_OTP_LENGTH):0{_OTP_LENGTH}d}"


def _check_and_increment_rate_limit(phone: str) -> None:
    """Raise ValidationError if the phone exceeded the per-window quota."""
    key = _rate_limit_key(phone)
    try:
        count = _redis.incr(key)
        if count == 1:
            _redis.expire(key, _RATE_LIMIT_WINDOW_SEC)
        if count > _RATE_LIMIT_MAX:
            raise ValidationError(
                message=(
                    f"Too many OTP requests. Please wait up to "
                    f"{_RATE_LIMIT_WINDOW_SEC // 60} minutes before retrying."
                )
            )
    except ValidationError:
        raise
    except Exception as exc:  # Redis unavailable — fail-open is acceptable for dev
        log.warning("otp_rate_limit_check_failed", error=str(exc))


async def _send_sms(phone: str, message: str) -> None:
    """Publish *message* to *phone* via AWS SNS, off the event loop."""
    settings = get_settings()
    sns = boto3.client("sns", region_name=settings.AWS_SNS_REGION)
    await asyncio.to_thread(
        sns.publish,
        PhoneNumber=phone,
        Message=message,
        MessageAttributes={
            "AWS.SNS.SMS.SMSType": {
                "DataType": "String",
                "StringValue": "Transactional",
            },
        },
    )


class OTPService:
    """Send & verify SMS one-time passwords."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def send(self, phone: str) -> None:
        _validate_phone(phone)
        _check_and_increment_rate_limit(phone)

        result = await self.db.execute(
            select(User).where(User.phone_number == phone)
        )
        user = result.scalar_one_or_none()
        if user is None:
            # Silently succeed to prevent enumeration. The UI shows a generic
            # "If that number is registered, an OTP has been sent" message.
            log.info("otp_send_unknown_phone", phone=phone)
            return
        if not user.is_active:
            log.info("otp_send_inactive_user", user_id=str(user.id))
            return

        otp = _generate_otp()
        user.otp_code_hash = hash_password(otp)
        user.otp_expires_at = datetime.now(UTC) + timedelta(minutes=_OTP_TTL_MINUTES)
        await self.db.flush()

        await _send_sms(
            phone,
            f"Your PetroLedger OTP is {otp}. Valid for {_OTP_TTL_MINUTES} minutes.",
        )
        log.info("otp_sent", user_id=str(user.id))

    async def verify(self, phone: str, otp: str) -> LoginResponse:
        _validate_phone(phone)

        result = await self.db.execute(
            select(User).where(User.phone_number == phone)
        )
        user = result.scalar_one_or_none()
        if user is None:
            raise AuthenticationError("No account found for this phone number.")

        if (
            user.otp_code_hash is None
            or user.otp_expires_at is None
            or user.otp_expires_at <= datetime.now(UTC)
        ):
            raise ValidationError(
                message="OTP has expired. Please request a new OTP."
            )

        if not verify_password(otp, user.otp_code_hash):
            raise ValidationError(message="Invalid OTP.")

        user.otp_code_hash = None
        user.otp_expires_at = None
        user.last_login = datetime.now(UTC)
        await self.db.flush()
        await self.db.refresh(user)

        token_data = {
            "sub": str(user.id),
            "role": user.role.value,
            "tenant_id": str(user.tenant_id),
            "org_id": str(user.org_id) if user.org_id else None,
        }
        return LoginResponse(
            access_token=create_access_token(token_data),
            refresh_token=create_refresh_token(token_data),
            user=UserResponse.model_validate(user),
        )
