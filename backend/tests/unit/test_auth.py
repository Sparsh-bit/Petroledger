"""PetroLedger — Authentication Tests.

Covers the core auth flows through the HTTP API:
  - Tenant registration (creates tenant + owner + returns tokens)
  - Duplicate registration rejection (409)
  - Login with valid credentials
  - Login with wrong password (401)
  - Login with unknown email (401)
  - Token refresh
  - Get current user profile (/me)
  - Logout + token blacklist enforcement
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

# ── Registration Payload ─────────────────────────────────────────────────────

_REG_PAYLOAD = {
    "tenant_name": "Sharma Fuels",
    "owner_name": "Amit Sharma",
    "owner_phone": "9876543210",
    "owner_email": "amit@sharmafuels.com",
    "password": "V3ryStr0ng!",
}


# ── Helpers ──────────────────────────────────────────────────────────────────


async def _register(client, payload: dict | None = None):
    """Register a tenant + owner and return the parsed response."""
    return await client.post(
        "/api/v1/auth/register",
        json=payload or _REG_PAYLOAD,
    )


async def _login(client, email: str = _REG_PAYLOAD["owner_email"],
                 password: str = _REG_PAYLOAD["password"]):
    """Login and return the parsed response."""
    return await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── Tests ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_register_creates_tenant_and_owner(test_client):
    """POST /auth/register — 201 with access & refresh tokens."""
    resp = await _register(test_client)
    assert resp.status_code == 201, resp.text

    body = resp.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["token_type"] == "bearer"
    assert body["tenant_id"]
    assert body["user_id"]


@pytest.mark.asyncio
async def test_register_duplicate_email_409(test_client):
    """Registering the same email twice → 409 DuplicateError."""
    resp1 = await _register(test_client)
    assert resp1.status_code == 201

    resp2 = await _register(test_client)
    assert resp2.status_code == 409


@pytest.mark.asyncio
async def test_login_valid_credentials(test_client):
    """POST /auth/login — 200 with tokens after a successful registration."""
    await _register(test_client)

    resp = await _login(test_client)
    assert resp.status_code == 200, resp.text

    body = resp.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password_401(test_client):
    """POST /auth/login with wrong password → 401."""
    await _register(test_client)

    resp = await _login(test_client, password="WrongPass123")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_unknown_email_401(test_client):
    """POST /auth/login with unregistered email → 401."""
    resp = await _login(test_client, email="nobody@example.com")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token(test_client):
    """POST /auth/refresh — exchange refresh token for new pair."""
    reg = await _register(test_client)
    refresh_token = reg.json()["refresh_token"]

    resp = await test_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert resp.status_code == 200, resp.text

    body = resp.json()
    assert body["access_token"]
    assert body["refresh_token"]
    # New tokens should differ from originals
    assert body["access_token"] != reg.json()["access_token"]


@pytest.mark.asyncio
async def test_refresh_invalid_token_401(test_client):
    """POST /auth/refresh with garbage token → 401."""
    resp = await test_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": "not-a-real-token"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_me(test_client):
    """GET /auth/me — returns current user profile."""
    reg = await _register(test_client)
    token = reg.json()["access_token"]

    resp = await test_client.get(
        "/api/v1/auth/me",
        headers=_auth_header(token),
    )
    assert resp.status_code == 200

    body = resp.json()
    assert body["email"] == _REG_PAYLOAD["owner_email"]
    assert body["role"] == "owner"
    assert body["is_active"] is True


@pytest.mark.asyncio
async def test_me_without_token_401(test_client):
    """GET /auth/me without Authorization header → 401/403."""
    resp = await test_client.get("/api/v1/auth/me")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_logout_blacklists_token(test_client):
    """POST /auth/logout — blacklists the access token.

    After logout, using the same token on /auth/me should fail.
    We mock the blacklist functions since Redis is not available in tests.
    """
    reg = await _register(test_client)
    token = reg.json()["access_token"]

    # Track which tokens get blacklisted
    blacklisted: set[str] = set()

    def mock_blacklist(tok, exp):
        blacklisted.add(tok)

    def mock_is_blacklisted(tok):
        return tok in blacklisted

    with patch("app.utils.token_blacklist.blacklist_token", mock_blacklist), \
         patch("app.api.deps.auth.is_blacklisted", mock_is_blacklisted):

        # Logout
        resp = await test_client.post(
            "/api/v1/auth/logout",
            headers=_auth_header(token),
        )
        assert resp.status_code == 200, resp.text
        assert "logged out" in resp.json()["message"].lower()

        # Using the same token after logout → should be rejected
        resp2 = await test_client.get(
            "/api/v1/auth/me",
            headers=_auth_header(token),
        )
        assert resp2.status_code == 401


@pytest.mark.asyncio
async def test_register_password_too_short_422(test_client):
    """Registration with password shorter than 8 chars → 422."""
    payload = {**_REG_PAYLOAD, "password": "short", "owner_email": "short@test.com"}
    resp = await _register(test_client, payload)
    assert resp.status_code == 422
