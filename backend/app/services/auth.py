"""PetroLedger — Authentication Service."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AuthenticationError,
    DuplicateError,
    NotFoundError,
    ValidationError,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.pump import Pump
from app.models.organization import Organization
from app.models.tenant import Tenant
from app.models.user import User, UserRole
from app.schemas.tenant import TenantRegistrationRequest
from app.schemas.user import LoginResponse, RegisterRequest, Token, UserCreate, UserResponse


class AuthService:
    """Handles registration, login, token refresh, and logout."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Tenant + Owner Registration (Multi-Tenant Sign-Up) ─────────────────

    async def register_tenant_owner(
        self, payload: TenantRegistrationRequest
    ) -> tuple[Tenant, User, Token]:
        """Create a new Tenant and its OWNER user in one atomic transaction.

        Returns (tenant, owner_user, token_pair) — the route serialises these.
        Raises DuplicateError if email is already registered.
        """
        # Check email uniqueness across users and tenants
        existing_user = await self.db.execute(
            select(User).where(User.email == payload.owner_email)
        )
        if existing_user.scalar_one_or_none() is not None:
            raise DuplicateError(f"Email '{payload.owner_email}' is already registered")

        existing_tenant = await self.db.execute(
            select(Tenant).where(Tenant.owner_email == payload.owner_email)
        )
        if existing_tenant.scalar_one_or_none() is not None:
            raise DuplicateError(f"A tenant with email '{payload.owner_email}' already exists")

        # Create Tenant (BASIC plan — 1 org)
        tenant = Tenant(
            name=payload.tenant_name,
            owner_name=payload.owner_name,
            owner_phone=payload.owner_phone,
            owner_email=payload.owner_email,
            subscription_plan="BASIC",
            max_orgs=1,
            is_active=True,
        )
        self.db.add(tenant)
        await self.db.flush()  # Populate tenant.id before FK reference

        # Create Owner user linked to the new tenant
        owner = User(
            email=payload.owner_email,
            phone=payload.owner_phone,
            hashed_password=hash_password(payload.password),
            role=UserRole.OWNER,
            tenant_id=tenant.id,
            org_id=None,  # Owners see ALL orgs in their tenant
            is_active=True,
        )
        self.db.add(owner)
        await self.db.flush()
        await self.db.refresh(owner)

        token_data = {
            "sub": str(owner.id),
            "role": owner.role.value,
            "tenant_id": str(owner.tenant_id),
            "org_id": None,
        }
        tokens = Token(
            access_token=create_access_token(token_data),
            refresh_token=create_refresh_token(token_data),
        )
        return tenant, owner, tokens

    # ── Legacy self-registration (kept for test compatibility) ───────────
    #
    # ``register_tenant_owner`` above is the canonical entry point for a new
    # dealer + owner account. This helper exists only to keep older tests
    # that exercised a pre-tenant path working. New tenant registrations
    # route through ``register_tenant_owner`` and receive ``UserRole.OWNER``.

    async def register_owner(self, payload: RegisterRequest, tenant_id: uuid.UUID) -> User:
        """Create the first user of an existing tenant as an OWNER.

        Used when a tenant row is created out-of-band (e.g. test fixtures or
        an internal provisioning script) and the owner account must be
        attached afterwards. No public route exposes this — it is called
        from tests and scripts only.
        """
        existing = await self.db.execute(
            select(User).where(User.email == payload.email)
        )
        if existing.scalar_one_or_none() is not None:
            raise DuplicateError(f"User with email '{payload.email}' already exists")

        user = User(
            email=payload.email,
            phone=payload.phone,
            hashed_password=hash_password(payload.password),
            role=UserRole.OWNER,
            tenant_id=tenant_id,
            org_id=None,
            is_active=True,
        )
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)
        return user

    # ── Staff Creation (RBAC-Gated) ────────────────────────────────────

    # Which roles each actor role is allowed to create within its tenant.
    _ROLE_CREATION_MATRIX: dict[UserRole, frozenset[UserRole]] = {
        UserRole.OWNER: frozenset(
            {UserRole.ADMIN, UserRole.MANAGER, UserRole.WORKER}
        ),
        UserRole.ADMIN: frozenset({UserRole.MANAGER, UserRole.WORKER}),
    }

    @classmethod
    def can_create_role(cls, actor_role: UserRole, target_role: UserRole) -> bool:
        """Return True when *actor_role* may create a user with *target_role*."""
        allowed = cls._ROLE_CREATION_MATRIX.get(actor_role, frozenset())
        return target_role in allowed

    async def create_staff_user(
        self,
        *,
        actor: User,
        email: str,
        password: str,
        role: UserRole,
        org_id: uuid.UUID | None = None,
    ) -> User:
        """Create a staff user on behalf of *actor*.

        Enforces:
          - actor.role can create target role (see _ROLE_CREATION_MATRIX)
          - email is globally unique
          - new user inherits actor.tenant_id (never cross-tenant)
        """
        from app.core.exceptions import AuthorizationError

        if not self.can_create_role(actor.role, role):
            raise AuthorizationError(
                f"Role '{actor.role.value}' cannot create users with role "
                f"'{role.value}'."
            )

        existing = await self.db.execute(select(User).where(User.email == email))
        if existing.scalar_one_or_none() is not None:
            raise DuplicateError(f"User with email '{email}' already exists")

        if len(password) < 8:
            raise ValidationError("Password must be at least 8 characters.")

        user = User(
            email=email,
            hashed_password=hash_password(password),
            role=role,
            tenant_id=actor.tenant_id,
            org_id=org_id or actor.org_id,
            is_active=True,
        )
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)
        return user

    # ── Register (internal — staff creation by authenticated owners) ─────

    async def register_user(self, payload: UserCreate) -> User:
        """Create a new user after checking for duplicates."""
        existing = await self.db.execute(
            select(User).where(User.email == payload.email)
        )
        if existing.scalar_one_or_none() is not None:
            raise DuplicateError(f"User with email '{payload.email}' already exists")

        user = User(
            email=payload.email,
            phone=payload.phone,
            hashed_password=hash_password(payload.password),
            role=payload.role,
            tenant_id=payload.tenant_id,
            org_id=payload.org_id,
            is_active=payload.is_active,
        )
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)
        return user

    # ── Login ───────────────────────────────────────────────────────────

    async def login(
        self, email: str, password: str, pump_code: str | None = None
    ) -> LoginResponse:
        """Authenticate user and return access + refresh tokens with user profile.

        If pump_code is provided, validates that the user's tenant owns a pump
        with that code. SUPERADMIN and PROVIDER users may skip pump_code.
        """
        result = await self.db.execute(
            select(User).where(User.email == email)
        )
        user = result.scalar_one_or_none()

        if user is None or not verify_password(password, user.hashed_password):
            raise AuthenticationError("Invalid email or password")

        if not user.is_active:
            raise AuthenticationError("Account is deactivated")

        # Pump-code validation for tenant users. Provider/superadmin skip.
        is_privileged = user.role in (UserRole.SUPERADMIN, UserRole.PROVIDER)
        if pump_code:
            normalized = pump_code.strip().upper()
            pump_result = await self.db.execute(
                select(Pump)
                .join(Organization, Organization.id == Pump.org_id)
                .where(Pump.code == normalized)
            )
            pump = pump_result.scalar_one_or_none()
            if pump is None:
                raise AuthenticationError("Invalid pump code for this account.")
            # Re-load org to check tenant ownership
            org_result = await self.db.execute(
                select(Organization).where(Organization.id == pump.org_id)
            )
            org = org_result.scalar_one_or_none()
            if org is None or org.tenant_id != user.tenant_id:
                raise AuthenticationError("Invalid pump code for this account.")
        elif not is_privileged:
            # Tenant-scoped users must supply a pump code when their tenant has any pumps.
            # Soft requirement: only reject if pumps exist for their tenant.
            exists_result = await self.db.execute(
                select(Pump.id)
                .join(Organization, Organization.id == Pump.org_id)
                .where(Organization.tenant_id == user.tenant_id)
                .limit(1)
            )
            if exists_result.first() is not None:
                raise AuthenticationError("Pump code is required for this account.")

        # Update last login
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

    # ── Refresh Token ───────────────────────────────────────────────────

    async def refresh_token(self, refresh_token: str) -> Token:
        """Issue a new token pair from a valid refresh token."""
        from jose import JWTError

        from app.utils.token_blacklist import is_blacklisted

        if is_blacklisted(refresh_token):
            raise AuthenticationError(
                "Refresh token has been revoked. Please log in again."
            )

        try:
            payload = decode_token(refresh_token)
        except JWTError as err:
            raise AuthenticationError("Invalid or expired refresh token") from err

        if payload.get("type") != "refresh":
            raise AuthenticationError("Token is not a refresh token")

        user_id = payload.get("sub")
        if user_id is None:
            raise AuthenticationError("Invalid token payload")

        result = await self.db.execute(
            select(User).where(User.id == uuid.UUID(user_id))
        )
        user = result.scalar_one_or_none()
        if user is None:
            # User record was deleted (e.g. tenant was purged). Surface as an
            # auth failure so the client's interceptor logs the user out
            # cleanly instead of showing a confusing 404.
            raise AuthenticationError(
                "Your account no longer exists. Please log in again."
            )
        if not user.is_active:
            raise AuthenticationError("Account is deactivated")

        token_data = {
            "sub": str(user.id),
            "role": user.role.value,
            "tenant_id": str(user.tenant_id),
            "org_id": str(user.org_id) if user.org_id else None,
        }
        return Token(
            access_token=create_access_token(token_data),
            refresh_token=create_refresh_token(token_data),
        )

    # ── Logout ──────────────────────────────────────────────────────────

    async def logout(
        self,
        user_id: str,
        access_token: str,
        refresh_token: str | None = None,
    ) -> dict:
        """Invalidate the current access token — and the refresh token if supplied.

        Both tokens are added to the Redis blacklist with TTL equal to their
        remaining lifetimes. Already-expired tokens are silently skipped.
        """
        from app.core.security import decode_token
        from app.utils.token_blacklist import blacklist_token

        try:
            payload = decode_token(access_token)
            blacklist_token(access_token, payload.get("exp", 0))
        except Exception:
            # Best-effort — still return success even if blacklisting fails
            pass

        if refresh_token:
            try:
                rpayload = decode_token(refresh_token)
                blacklist_token(refresh_token, rpayload.get("exp", 0))
            except Exception:
                # Token may already be expired or malformed — treat as success
                pass

        return {"message": "Successfully logged out", "user_id": user_id}

    # ── Google OAuth ────────────────────────────────────────────────────

    async def google_login(self, id_token_str: str) -> LoginResponse:
        """Verify a Google ID token and issue JWT tokens.

        Flow:
          1. Verify signature + audience (GOOGLE_CLIENT_ID) against Google's JWKS.
          2. Lookup user by email. If local-password account exists: reject.
          3. If google user exists: refresh `google_id`, issue tokens.
          4. If no user exists: reject (invite-only platform — no self-sign-up).
        """
        from google.auth.transport import requests as google_requests  # type: ignore[import-untyped]
        from google.oauth2 import id_token as google_id_token  # type: ignore[import-untyped]

        from app.core.config import get_settings

        settings = get_settings()
        if not settings.GOOGLE_CLIENT_ID:
            raise ValidationError(
                message="Google OAuth is not configured on this server."
            )

        try:
            idinfo = google_id_token.verify_oauth2_token(
                id_token_str,
                google_requests.Request(),
                settings.GOOGLE_CLIENT_ID,
            )
        except ValueError as err:
            raise AuthenticationError(f"Invalid Google token: {err}") from err

        email = idinfo.get("email")
        google_sub = idinfo.get("sub")
        if not email or not google_sub:
            raise AuthenticationError("Google token missing email or subject claim")

        result = await self.db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if user is None:
            raise AuthenticationError(
                "No PetroLedger account exists for this Google email. "
                "Ask your organisation owner to invite you."
            )

        if user.auth_provider == "local":
            raise ValidationError(
                message=(
                    "This email is registered with a password. "
                    "Please sign in with your password."
                )
            )

        if not user.is_active:
            raise AuthenticationError("Account is deactivated")

        # Refresh the google_id in case it was not previously stored
        if user.google_id != google_sub:
            user.google_id = google_sub
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

