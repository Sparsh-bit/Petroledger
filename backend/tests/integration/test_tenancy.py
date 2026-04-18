"""PetroLedger — Multi-Tenancy Integration Tests.

Covers:
  - Owner inviting a team member (admin, manager, worker)
  - Non-owner invite rejection (403)
  - Tenant isolation (cross-tenant access denied)
"""

from __future__ import annotations

import pytest

# ── Registration Payloads ────────────────────────────────────────────────────

_TENANT_A = {
    "tenant_name": "Tenant Alpha",
    "owner_name": "Alpha Owner",
    "owner_phone": "9000000001",
    "owner_email": "owner-a@alpha.com",
    "password": "AlphaStr0ng!",
}

_TENANT_B = {
    "tenant_name": "Tenant Beta",
    "owner_name": "Beta Owner",
    "owner_phone": "9000000002",
    "owner_email": "owner-b@beta.com",
    "password": "BetaStr0ng!!",
}


# ── Helpers ──────────────────────────────────────────────────────────────────


async def _register(client, payload: dict):
    resp = await client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _create_org(client, token: str, name: str = "Station-1"):
    """Create an org under the authenticated user's tenant."""
    resp = await client.post(
        "/api/v1/organizations/",
        json={"name": name, "contact_email": f"{name.lower().replace(' ', '-')}@test.com"},
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── Tests ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_invite_manager(test_client):
    """OWNER can invite a manager to a specific organization."""
    reg = await _register(test_client, _TENANT_A)
    token = reg["access_token"]

    # Create an org first (invite requires org_id for manager role)
    org = await _create_org(test_client, token)

    resp = await test_client.post(
        "/api/v1/tenants/invite-user",
        json={
            "full_name": "Manager One",
            "email": "manager@alpha.com",
            "phone": "9000000010",
            "role": "manager",
            "org_id": org["id"],
        },
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text

    body = resp.json()
    assert body["email"] == "manager@alpha.com"
    assert body["role"] == "manager"
    assert body["temporary_password"]  # non-empty password generated


@pytest.mark.asyncio
async def test_invite_admin_no_org_id(test_client):
    """OWNER can invite an admin without org_id (admin sees all orgs)."""
    reg = await _register(test_client, _TENANT_A)
    token = reg["access_token"]

    resp = await test_client.post(
        "/api/v1/tenants/invite-user",
        json={
            "full_name": "Admin Person",
            "email": "admin@alpha.com",
            "phone": "9000000020",
            "role": "admin",
            "org_id": None,
        },
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["role"] == "admin"


@pytest.mark.asyncio
async def test_invite_forbidden_for_non_owner(test_client):
    """Non-OWNER user cannot invite — should get 403."""
    reg = await _register(test_client, _TENANT_A)
    owner_token = reg["access_token"]

    # Create org + invite a manager
    org = await _create_org(test_client, owner_token)

    invite_resp = await test_client.post(
        "/api/v1/tenants/invite-user",
        json={
            "full_name": "Mgr",
            "email": "mgr@alpha.com",
            "phone": "9000000030",
            "role": "manager",
            "org_id": org["id"],
        },
        headers=_auth(owner_token),
    )
    assert invite_resp.status_code == 200

    # Login as the manager
    temp_pw = invite_resp.json()["temporary_password"]
    login_resp = await test_client.post(
        "/api/v1/auth/login",
        json={"email": "mgr@alpha.com", "password": temp_pw},
    )
    assert login_resp.status_code == 200
    mgr_token = login_resp.json()["access_token"]

    # Manager tries to invite someone → should be 403
    resp = await test_client.post(
        "/api/v1/tenants/invite-user",
        json={
            "full_name": "Somebody",
            "email": "somebody@alpha.com",
            "phone": "9000000040",
            "role": "worker",
            "org_id": org["id"],
        },
        headers=_auth(mgr_token),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_tenant_isolation(test_client):
    """Tenant A's owner cannot see Tenant B's organizations."""
    reg_a = await _register(test_client, _TENANT_A)
    reg_b = await _register(test_client, _TENANT_B)

    token_a = reg_a["access_token"]
    token_b = reg_b["access_token"]

    # Each creates an org in their own tenant
    await _create_org(test_client, token_a, "Alpha Station")
    await _create_org(test_client, token_b, "Beta Station")

    # Tenant A lists orgs — should only see their own
    resp_a = await test_client.get(
        "/api/v1/organizations/",
        headers=_auth(token_a),
    )
    assert resp_a.status_code == 200
    data_a = resp_a.json()

    # Handle both paginated and list responses
    items_a = data_a.get("data", data_a) if isinstance(data_a, dict) else data_a
    names_a = [o["name"] for o in items_a]
    assert "Alpha Station" in names_a
    assert "Beta Station" not in names_a

    # Tenant B lists orgs — should only see their own
    resp_b = await test_client.get(
        "/api/v1/organizations/",
        headers=_auth(token_b),
    )
    assert resp_b.status_code == 200
    data_b = resp_b.json()

    items_b = data_b.get("data", data_b) if isinstance(data_b, dict) else data_b
    names_b = [o["name"] for o in items_b]
    assert "Beta Station" in names_b
    assert "Alpha Station" not in names_b
