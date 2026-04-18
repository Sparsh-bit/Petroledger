"""
Integration tests for the Reports API endpoints.

GET /api/v1/reports/shift/{shift_id}  → PDF for a single shift
GET /api/v1/reports/daily             → PDF or Excel daily summary

The report service layer (ShiftReportService / DailyReportService) is
mocked to return a real temp file, keeping tests fast and dependency-free
(no WeasyPrint / openpyxl required) while exercising the full HTTP →
auth → RBAC → DB tenant-check → response path.

IMPORTANT: All JWT tokens must use ``sample_user.id`` as the ``sub`` claim.
``get_current_active_user`` performs a live DB lookup — random UUIDs return 401.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


# ── Helpers ──────────────────────────────────────────────────────────────


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _token_for(user) -> str:
    from app.core.security import create_access_token
    # UserRole is a StrEnum; SQLite may return a plain str — str() covers both
    return create_access_token({"sub": str(user.id), "role": str(user.role)})


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def tmp_pdf(tmp_path) -> Path:
    """A real temp file that stands in for a generated PDF report."""
    p = tmp_path / "test_report.pdf"
    p.write_bytes(b"%PDF-1.4 fake")
    return p


@pytest.fixture
def tmp_xlsx(tmp_path) -> Path:
    """A real temp file that stands in for a generated Excel report."""
    p = tmp_path / "test_report.xlsx"
    p.write_bytes(b"PK\x03\x04 fake xlsx")
    return p


# ── GET /api/v1/reports/shift/{shift_id} ─────────────────────────────────


@pytest.mark.asyncio
class TestShiftReport:
    ENDPOINT = "/api/v1/reports/shift/{shift_id}"

    async def test_no_auth_returns_401(
        self,
        test_client: AsyncClient,
        sample_shift,
    ):
        """Missing Authorization header → 401."""
        resp = await test_client.get(self.ENDPOINT.format(shift_id=sample_shift.id))
        assert resp.status_code == 401

    async def test_worker_role_forbidden(
        self,
        test_client: AsyncClient,
        async_db_session: AsyncSession,
        sample_shift,
        sample_tenant,
        sample_org,
    ):
        """A WORKER role cannot download shift reports — 403."""
        from app.models.user import UserRole
        from tests.fixtures.factories import UserFactory

        worker = await UserFactory.create(
            tenant_id=sample_tenant.id,
            role=UserRole.WORKER,
            org_id=sample_org.id,
        )
        resp = await test_client.get(
            self.ENDPOINT.format(shift_id=sample_shift.id),
            headers=_auth(_token_for(worker)),
        )
        assert resp.status_code == 403

    async def test_manager_role_forbidden(
        self,
        test_client: AsyncClient,
        async_db_session: AsyncSession,
        sample_shift,
        sample_tenant,
        sample_org,
    ):
        """A MANAGER role cannot download shift reports — 403."""
        from app.models.user import UserRole
        from tests.fixtures.factories import UserFactory

        manager = await UserFactory.create(
            tenant_id=sample_tenant.id,
            role=UserRole.MANAGER,
            org_id=sample_org.id,
        )
        resp = await test_client.get(
            self.ENDPOINT.format(shift_id=sample_shift.id),
            headers=_auth(_token_for(manager)),
        )
        assert resp.status_code == 403

    async def test_unknown_shift_returns_404(
        self,
        test_client: AsyncClient,
        async_db_session: AsyncSession,
        sample_user,
    ):
        """Non-existent shift_id → 404."""
        resp = await test_client.get(
            self.ENDPOINT.format(shift_id=uuid.uuid4()),
            headers=_auth(_token_for(sample_user)),
        )
        assert resp.status_code == 404

    async def test_other_tenant_shift_returns_404(
        self,
        test_client: AsyncClient,
        async_db_session: AsyncSession,
        sample_user,
    ):
        """Shift belonging to a different tenant → 404 (no cross-tenant leak)."""
        from tests.fixtures.factories import (
            OrganizationFactory,
            PumpFactory,
            ShiftFactory,
            TenantFactory,
            WorkerFactory,
        )

        other_tenant = await TenantFactory.create()
        other_org = await OrganizationFactory.create(tenant_id=other_tenant.id)
        other_pump = await PumpFactory.create(org_id=other_org.id)
        other_worker = await WorkerFactory.create(pump_id=other_pump.id)
        other_shift = await ShiftFactory.create(
            pump_id=other_pump.id, worker_id=other_worker.id
        )

        resp = await test_client.get(
            self.ENDPOINT.format(shift_id=other_shift.id),
            headers=_auth(_token_for(sample_user)),
        )
        assert resp.status_code == 404

    async def test_success_returns_pdf(
        self,
        test_client: AsyncClient,
        async_db_session: AsyncSession,
        sample_shift,
        sample_user,
        tmp_pdf: Path,
    ):
        """OWNER with a valid shift → 200 with PDF content-type and attachment header."""
        with patch(
            "app.api.v1.reports.routes.ShiftReportService.generate",
            new_callable=AsyncMock,
            return_value=tmp_pdf,
        ):
            resp = await test_client.get(
                self.ENDPOINT.format(shift_id=sample_shift.id),
                headers=_auth(_token_for(sample_user)),
            )

        assert resp.status_code == 200
        assert "pdf" in resp.headers.get("content-type", "")
        assert "attachment" in resp.headers.get("content-disposition", "")

    async def test_admin_role_can_download(
        self,
        test_client: AsyncClient,
        async_db_session: AsyncSession,
        sample_shift,
        sample_tenant,
        sample_org,
        tmp_pdf: Path,
    ):
        """ADMIN role is also permitted to download shift reports."""
        from app.models.user import UserRole
        from tests.fixtures.factories import UserFactory

        admin = await UserFactory.create(
            tenant_id=sample_tenant.id,
            role=UserRole.ADMIN,
            org_id=sample_org.id,
        )
        with patch(
            "app.api.v1.reports.routes.ShiftReportService.generate",
            new_callable=AsyncMock,
            return_value=tmp_pdf,
        ):
            resp = await test_client.get(
                self.ENDPOINT.format(shift_id=sample_shift.id),
                headers=_auth(_token_for(admin)),
            )

        assert resp.status_code == 200


# ── GET /api/v1/reports/daily ─────────────────────────────────────────────


@pytest.mark.asyncio
class TestDailyReport:
    ENDPOINT = "/api/v1/reports/daily"

    async def test_no_auth_returns_401(
        self,
        test_client: AsyncClient,
        sample_org,
    ):
        """Missing Authorization header → 401."""
        resp = await test_client.get(
            self.ENDPOINT,
            params={"site_id": str(sample_org.id), "report_date": "2026-04-01"},
        )
        assert resp.status_code == 401

    async def test_invalid_format_returns_422(
        self,
        test_client: AsyncClient,
        async_db_session: AsyncSession,
        sample_org,
        sample_user,
    ):
        """Unsupported format= value → 422."""
        resp = await test_client.get(
            self.ENDPOINT,
            params={
                "site_id": str(sample_org.id),
                "report_date": "2026-04-01",
                "format": "docx",
            },
            headers=_auth(_token_for(sample_user)),
        )
        assert resp.status_code == 422

    async def test_unknown_org_returns_404(
        self,
        test_client: AsyncClient,
        async_db_session: AsyncSession,
        sample_user,
    ):
        """Non-existent site_id → 404."""
        resp = await test_client.get(
            self.ENDPOINT,
            params={"site_id": str(uuid.uuid4()), "report_date": "2026-04-01"},
            headers=_auth(_token_for(sample_user)),
        )
        assert resp.status_code == 404

    async def test_other_tenant_org_returns_404(
        self,
        test_client: AsyncClient,
        async_db_session: AsyncSession,
        sample_user,
    ):
        """Org belonging to a different tenant → 404."""
        from tests.fixtures.factories import OrganizationFactory, TenantFactory

        other_tenant = await TenantFactory.create()
        other_org = await OrganizationFactory.create(tenant_id=other_tenant.id)

        resp = await test_client.get(
            self.ENDPOINT,
            params={"site_id": str(other_org.id), "report_date": "2026-04-01"},
            headers=_auth(_token_for(sample_user)),
        )
        assert resp.status_code == 404

    async def test_pdf_success(
        self,
        test_client: AsyncClient,
        async_db_session: AsyncSession,
        sample_org,
        sample_user,
        tmp_pdf: Path,
    ):
        """OWNER + valid org → 200 PDF response."""
        with patch(
            "app.api.v1.reports.routes.DailyReportService.generate_pdf",
            new_callable=AsyncMock,
            return_value=tmp_pdf,
        ):
            resp = await test_client.get(
                self.ENDPOINT,
                params={
                    "site_id": str(sample_org.id),
                    "report_date": "2026-04-01",
                    "format": "pdf",
                },
                headers=_auth(_token_for(sample_user)),
            )

        assert resp.status_code == 200
        assert "pdf" in resp.headers.get("content-type", "")
        assert "attachment" in resp.headers.get("content-disposition", "")

    async def test_excel_success(
        self,
        test_client: AsyncClient,
        async_db_session: AsyncSession,
        sample_org,
        sample_user,
        tmp_xlsx: Path,
    ):
        """OWNER + valid org + format=excel → 200 xlsx response."""
        with patch(
            "app.api.v1.reports.routes.DailyReportService.generate_excel",
            new_callable=AsyncMock,
            return_value=tmp_xlsx,
        ):
            resp = await test_client.get(
                self.ENDPOINT,
                params={
                    "site_id": str(sample_org.id),
                    "report_date": "2026-04-01",
                    "format": "excel",
                },
                headers=_auth(_token_for(sample_user)),
            )

        assert resp.status_code == 200
        ct = resp.headers.get("content-type", "")
        assert "spreadsheetml" in ct or "octet-stream" in ct
        assert "attachment" in resp.headers.get("content-disposition", "")

    async def test_worker_role_forbidden(
        self,
        test_client: AsyncClient,
        async_db_session: AsyncSession,
        sample_org,
        sample_tenant,
    ):
        """WORKER role cannot download daily reports — 403."""
        from app.models.user import UserRole
        from tests.fixtures.factories import UserFactory

        worker = await UserFactory.create(
            tenant_id=sample_tenant.id,
            role=UserRole.WORKER,
            org_id=sample_org.id,
        )
        resp = await test_client.get(
            self.ENDPOINT,
            params={"site_id": str(sample_org.id), "report_date": "2026-04-01"},
            headers=_auth(_token_for(worker)),
        )
        assert resp.status_code == 403

    async def test_default_format_is_pdf(
        self,
        test_client: AsyncClient,
        async_db_session: AsyncSession,
        sample_org,
        sample_user,
        tmp_pdf: Path,
    ):
        """Omitting format= defaults to PDF."""
        with patch(
            "app.api.v1.reports.routes.DailyReportService.generate_pdf",
            new_callable=AsyncMock,
            return_value=tmp_pdf,
        ) as mock_pdf:
            resp = await test_client.get(
                self.ENDPOINT,
                params={"site_id": str(sample_org.id), "report_date": "2026-04-01"},
                headers=_auth(_token_for(sample_user)),
            )

        assert resp.status_code == 200
        mock_pdf.assert_called_once()
