"""PetroLedger — Authentication Routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import bearer_scheme, get_current_active_user
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.models.user import User
from app.schemas.tenant import TenantRegistrationRequest, TenantRegistrationResponse
from app.schemas.user import (
    LoginResponse,
    Token,
    TokenRefresh,
    UserLogin,
    UserResponse,
)
from app.services.auth import AuthService

router = APIRouter()


# ── Helper Schemas (route-local) ────────────────────────────────────────────


class GoogleAuthRequest(BaseModel):
    """Payload from Google OAuth callback."""
    id_token: str


class OTPSendRequest(BaseModel):
    """Request to send an SMS OTP."""
    phone_number: str


class OTPVerifyRequest(BaseModel):
    """Request to verify an OTP."""
    phone_number: str
    otp: str


class MessageResponse(BaseModel):
    """Generic message response."""
    message: str


class LogoutRequest(BaseModel):
    """Logout payload — optional refresh token to revoke alongside the access token."""
    refresh_token: str | None = None


class PasswordResetRequest(BaseModel):
    email: str


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str


class PasswordChangeRequest(BaseModel):
    old_password: str
    new_password: str


# ── POST /register ───────────────────────────────────────────────────────────


@router.post(
    "/register",
    response_model=TenantRegistrationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new tenant (dealer) and owner account",
)
@limiter.limit("5/hour")
async def register(
    request: Request,
    payload: TenantRegistrationRequest,
    db: AsyncSession = Depends(get_db),
) -> TenantRegistrationResponse:
    """
    Sign up as a new dealer.

    Creates both a Tenant entity and an OWNER user in one atomic transaction.
    Returns JWT tokens immediately — no separate login step needed.

    Subscription defaults to BASIC (1 pump location allowed).
    """
    service = AuthService(db)
    tenant, owner, tokens = await service.register_tenant_owner(payload)
    await db.commit()

    return TenantRegistrationResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        tenant_id=str(tenant.id),
        user_id=str(owner.id),
    )


# ── POST /login ──────────────────────────────────────────────────────────────


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Login with email and password",
)
@limiter.limit("10/minute")
async def login(
    request: Request,
    payload: UserLogin,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    """Authenticate and receive access + refresh tokens."""
    service = AuthService(db)
    return await service.login(
        email=payload.email,
        password=payload.password,
        pump_code=payload.pump_code,
    )


# ── POST /refresh ────────────────────────────────────────────────────────────


@router.post(
    "/refresh",
    response_model=Token,
    summary="Refresh access token",
)
@limiter.limit("20/minute")
async def refresh(
    request: Request,
    payload: TokenRefresh,
    db: AsyncSession = Depends(get_db),
) -> Token:
    """Exchange a valid refresh token for a new token pair."""
    service = AuthService(db)
    return await service.refresh_token(refresh_token=payload.refresh_token)


# ── POST /logout ─────────────────────────────────────────────────────────────


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Logout (blacklist access token)",
)
async def logout(
    payload: LogoutRequest | None = None,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> MessageResponse:
    """Blacklist the current access token (and refresh token if supplied)."""
    service = AuthService(db)
    result = await service.logout(
        user_id=str(current_user.id),
        access_token=credentials.credentials,
        refresh_token=payload.refresh_token if payload else None,
    )
    return MessageResponse(message=result["message"])


# ── POST /google ─────────────────────────────────────────────────────────────


@router.post(
    "/google",
    response_model=LoginResponse,
    summary="Google OAuth login",
)
async def google_auth(
    payload: GoogleAuthRequest,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    """Exchange a Google ID token for PetroLedger access + refresh tokens.

    The user must already exist in PetroLedger (invite-only). If the account
    was originally created with a password, the user is instructed to use
    password sign-in instead.
    """
    service = AuthService(db)
    response = await service.google_login(id_token_str=payload.id_token)
    await db.commit()
    return response


# ── POST /otp/send ───────────────────────────────────────────────────────────


@router.post(
    "/otp/send",
    response_model=MessageResponse,
    summary="Send SMS OTP to phone",
)
@limiter.limit("10/15minutes")
async def otp_send(
    request: Request,
    payload: OTPSendRequest,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Generate and send a one-time password via SMS (AWS SNS).

    Rate-limited to 3 requests per phone per 15 minutes. Always returns
    HTTP 200 with a generic message — never reveals whether the number
    is registered.
    """
    from app.services.otp import OTPService

    service = OTPService(db)
    await service.send(phone=payload.phone_number)
    await db.commit()
    return MessageResponse(
        message="If the number is registered, an OTP has been sent."
    )


# ── POST /otp/verify ─────────────────────────────────────────────────────────


@router.post(
    "/otp/verify",
    response_model=LoginResponse,
    summary="Verify OTP and get tokens",
)
async def otp_verify(
    payload: OTPVerifyRequest,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    """Verify an SMS OTP and return PetroLedger access + refresh tokens."""
    from app.services.otp import OTPService

    service = OTPService(db)
    response = await service.verify(phone=payload.phone_number, otp=payload.otp)
    await db.commit()
    return response


# ── POST /password-reset/request ─────────────────────────────────────────────


@router.post(
    "/password-reset/request",
    response_model=MessageResponse,
    summary="Request a password-reset email",
)
@limiter.limit("5/hour")
async def password_reset_request(
    request: Request,
    payload: PasswordResetRequest,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Send a password reset link to the given email. Enumeration-safe: always 200."""
    from app.services.password_reset import PasswordResetService

    service = PasswordResetService(db)
    await service.request(email=payload.email)
    await db.commit()
    return MessageResponse(
        message="If the email is registered, a reset link has been sent."
    )


# ── POST /password-reset/confirm ─────────────────────────────────────────────


@router.post(
    "/password-reset/confirm",
    response_model=MessageResponse,
    summary="Confirm a password reset with the emailed token",
)
async def password_reset_confirm(
    payload: PasswordResetConfirm,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Validate the token and rotate the password. Invalidates all existing JWTs."""
    from app.services.password_reset import PasswordResetService

    service = PasswordResetService(db)
    await service.confirm(token=payload.token, new_password=payload.new_password)
    await db.commit()
    return MessageResponse(
        message="Password updated. Please log in with your new password."
    )


# ── GET /me ───────────────────────────────────────────────────────────────────


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user profile",
)
async def me(
    current_user: User = Depends(get_current_active_user),
) -> UserResponse:
    """Return the currently authenticated user's profile."""
    return UserResponse.model_validate(current_user)


# ── POST /password-change ───────────────────────────────────────────────────


@router.post(
    "/password-change",
    response_model=MessageResponse,
    summary="Change the password for the authenticated user",
)
async def password_change(
    payload: PasswordChangeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> MessageResponse:
    """Verify old password and rotate to new password."""
    from fastapi import HTTPException, status as http_status

    from app.core.security import hash_password, verify_password

    if not verify_password(payload.old_password, current_user.hashed_password):
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect.",
        )
    if len(payload.new_password) < 8:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="New password must be at least 8 characters.",
        )
    current_user.hashed_password = hash_password(payload.new_password)
    db.add(current_user)
    await db.commit()
    return MessageResponse(message="Password updated.")
