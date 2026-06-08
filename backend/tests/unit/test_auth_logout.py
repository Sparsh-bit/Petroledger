"""Refresh-token revocation on logout.

A user who calls POST /auth/logout with their refresh token in the body
must no longer be able to mint new access tokens from that refresh token.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest


_REG_PAYLOAD = {
    "tenant_name": "Logout Test Fuels",
    "owner_name": "Logout Tester",
    "owner_phone": "9876500001",
    "owner_email": "logout-test@fuels.com",
    "password": "V3ryStr0ng!",
}


@pytest.mark.asyncio
async def test_refresh_token_revoked_after_logout(test_client):
    resp = await test_client.post("/api/v1/auth/register", json=_REG_PAYLOAD)
    assert resp.status_code == 201
    body = resp.json()
    access_token = body["access_token"]
    refresh_token = body["refresh_token"]

    blacklisted: set[str] = set()

    def _blacklist(tok, _exp):
        blacklisted.add(tok)

    def _is_blacklisted(tok):
        return tok in blacklisted

    with patch("app.utils.token_blacklist.blacklist_token", _blacklist), \
         patch("app.utils.token_blacklist.is_blacklisted", _is_blacklisted):

        logout = await test_client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"refresh_token": refresh_token},
        )
        assert logout.status_code == 200

        # Refresh token must now be rejected.
        refresh = await test_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert refresh.status_code == 401
        assert "revoked" in refresh.json().get("detail", "").lower() \
            or "revoked" in str(refresh.json()).lower()
