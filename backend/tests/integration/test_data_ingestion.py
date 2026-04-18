"""
PetroLedger — Integration Tests for Data-Ingestion API Endpoints.

Tests the full HTTP request → response cycle with:
    - Real FastAPI app + HTTPX AsyncClient
    - In-memory SQLite database (via conftest fixtures)
    - Mocked Celery task dispatch (.delay)
    - Mocked Redis (no real Redis needed)
    - Real JWT auth (token signed with test SECRET_KEY)
"""

from __future__ import annotations

import io
import uuid
from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════


def _create_token(user_id: str | uuid.UUID) -> str:
    """Create a valid JWT access token for the given user_id."""
    from app.core.security import create_access_token

    return create_access_token({"sub": str(user_id)})


def _csv_upload(content: str, filename: str = "test.csv"):
    """Build a multipart file tuple for an UploadFile."""
    return {"file": (filename, io.BytesIO(content.encode()), "text/csv")}


def _img_upload(filename: str = "slip.png"):
    """Build a minimal PNG multipart upload."""
    from PIL import Image

    img = Image.new("RGB", (10, 10), color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return {"file": (filename, buf, "image/png")}


def _json_upload(content: str, filename: str = "log.json"):
    """Build a JSON file multipart upload."""
    return {"file": (filename, io.BytesIO(content.encode()), "application/json")}


# ═══════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════


@pytest.fixture
def _mock_celery():
    """Patch all three Celery task .delay() methods to prevent actual queuing."""
    with (
        patch(
            "app.api.v1.data_ingestion.routes.process_upi_csv.delay",
            return_value=MagicMock(id="mock-task-id"),
        ) as upi,
        patch(
            "app.api.v1.data_ingestion.routes.process_pos_slip.delay",
            return_value=MagicMock(id="mock-task-id"),
        ) as pos,
        patch(
            "app.api.v1.data_ingestion.routes.process_pump_log.delay",
            return_value=MagicMock(id="mock-task-id"),
        ) as pump,
    ):
        yield {"upi": upi, "pos": pos, "pump": pump}


@pytest.fixture
def _mock_redis():
    """Patch the Redis client used in routes for job status."""
    mock = MagicMock()
    mock.hgetall.return_value = {}
    with patch("app.api.v1.data_ingestion.routes._redis", mock):
        yield mock


@pytest.fixture
def _mock_s3():
    """Patch S3Service.upload_file_async to prevent real AWS calls."""
    async def _fake_upload(_content, _key):
        return "ingestion/mock-key/file.csv"
    with patch(
        "app.api.v1.data_ingestion.routes._s3.upload_file_async",
        side_effect=_fake_upload,
    ) as mock:
        yield mock


# ═══════════════════════════════════════════════════════════════════════
# POST /data-ingestion/upi-csv
# ═══════════════════════════════════════════════════════════════════════


class TestUploadUPICSV:
    """POST /api/v1/data-ingestion/upi-csv."""

    ENDPOINT = "/api/v1/data-ingestion/upi-csv"

    async def test_valid_upload(
        self, test_client: AsyncClient, sample_user, sample_shift, _mock_celery, _mock_redis, _mock_s3
    ):
        """Valid CSV + auth → 202 Accepted with job_id."""
        token = _create_token(sample_user.id)
        shift_id = str(sample_shift.id)

        resp = await test_client.post(
            self.ENDPOINT,
            files=_csv_upload("Date,Txn ID,Debit,Credit,Balance\n01/01/2026,TX1,,100,1000\n"),
            data={"shift_id": shift_id},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 202
        body = resp.json()
        assert body["status"] == "queued"
        assert "job_id" in body
        _mock_celery["upi"].assert_called_once()

    async def test_no_auth_returns_403(self, test_client: AsyncClient, _mock_celery, _mock_redis):
        """Missing Authorization header → 401."""
        resp = await test_client.post(
            self.ENDPOINT,
            files=_csv_upload("a,b,c\n1,2,3\n"),
            data={"shift_id": str(uuid.uuid4())},
        )
        assert resp.status_code == 401

    async def test_invalid_ext_returns_422(
        self, test_client: AsyncClient, sample_user, sample_shift, _mock_celery, _mock_redis
    ):
        """Non-CSV extension → 422 validation error."""
        token = _create_token(sample_user.id)

        resp = await test_client.post(
            self.ENDPOINT,
            files={"file": ("data.xlsx", io.BytesIO(b"data"), "application/octet-stream")},
            data={"shift_id": str(sample_shift.id)},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422

    async def test_invalid_shift_id_returns_422(
        self, test_client: AsyncClient, sample_user, _mock_celery, _mock_redis
    ):
        """Malformed shift_id → 422."""
        token = _create_token(sample_user.id)

        resp = await test_client.post(
            self.ENDPOINT,
            files=_csv_upload("a,b\n1,2\n"),
            data={"shift_id": "not-a-uuid"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════════════
# POST /data-ingestion/pos-slip
# ═══════════════════════════════════════════════════════════════════════


class TestUploadPOSSlip:
    """POST /api/v1/data-ingestion/pos-slip."""

    ENDPOINT = "/api/v1/data-ingestion/pos-slip"

    async def test_valid_upload(
        self, test_client: AsyncClient, sample_user, sample_shift, _mock_celery, _mock_redis, _mock_s3
    ):
        """Valid PNG + auth → 202 Accepted queued."""
        token = _create_token(sample_user.id)

        resp = await test_client.post(
            self.ENDPOINT,
            files=_img_upload("receipt.png"),
            data={"shift_id": str(sample_shift.id)},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 202
        body = resp.json()
        assert body["status"] == "queued"
        _mock_celery["pos"].assert_called_once()

    async def test_invalid_ext_returns_422(
        self, test_client: AsyncClient, sample_user, sample_shift, _mock_celery, _mock_redis
    ):
        """Non-image extension → 422."""
        token = _create_token(sample_user.id)

        resp = await test_client.post(
            self.ENDPOINT,
            files={"file": ("slip.docx", io.BytesIO(b"data"), "application/octet-stream")},
            data={"shift_id": str(sample_shift.id)},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════════════
# POST /data-ingestion/pump-logs
# ═══════════════════════════════════════════════════════════════════════


class TestUploadPumpLogs:
    """POST /api/v1/data-ingestion/pump-logs."""

    ENDPOINT = "/api/v1/data-ingestion/pump-logs"

    async def test_valid_upload(
        self, test_client: AsyncClient, sample_user, sample_shift, sample_pump, _mock_celery, _mock_redis, _mock_s3
    ):
        """Valid JSON log + auth → 202 Accepted queued."""
        token = _create_token(sample_user.id)
        log_data = '[{"nozzle": 1, "start": 100, "end": 150}]'

        resp = await test_client.post(
            self.ENDPOINT,
            files=_json_upload(log_data, "log.json"),
            data={
                "shift_id": str(sample_shift.id),
                "pump_id": str(sample_pump.id),
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 202
        body = resp.json()
        assert body["status"] == "queued"
        _mock_celery["pump"].assert_called_once()

    async def test_missing_pump_id_returns_422(
        self, test_client: AsyncClient, sample_user, sample_shift, _mock_celery, _mock_redis
    ):
        """pump_id missing → 422."""
        token = _create_token(sample_user.id)

        resp = await test_client.post(
            self.ENDPOINT,
            files=_json_upload("[]", "log.json"),
            data={"shift_id": str(sample_shift.id)},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════════════
# GET /data-ingestion/status/{job_id}
# ═══════════════════════════════════════════════════════════════════════


class TestGetJobStatus:
    """GET /api/v1/data-ingestion/status/{job_id}."""

    ENDPOINT = "/api/v1/data-ingestion/status/{job_id}"

    async def test_completed_job(
        self, test_client: AsyncClient, sample_user, _mock_redis
    ):
        """Existing completed job → 200 with result."""
        token = _create_token(sample_user.id)
        job_id = str(uuid.uuid4())

        import json

        _mock_redis.hgetall.return_value = {
            "status": "completed",
            "progress": "100",
            "result": json.dumps({
                "total_records": 10,
                "processed_records": 8,
                "failed_records": 0,
                "duplicates_skipped": 2,
            }),
            "error": "",
            "created_at": "2026-03-05T12:00:00+05:30",
        }

        resp = await test_client.get(
            self.ENDPOINT.format(job_id=job_id),
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "completed"
        assert body["progress"] == 100
        assert body["result"]["total_records"] == 10
        assert body["result"]["duplicates_skipped"] == 2

    async def test_not_found_job(
        self, test_client: AsyncClient, sample_user, _mock_redis
    ):
        """Non-existent job_id → 422 (ValidationError)."""
        token = _create_token(sample_user.id)
        _mock_redis.hgetall.return_value = {}

        resp = await test_client.get(
            self.ENDPOINT.format(job_id=str(uuid.uuid4())),
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422

    async def test_failed_job(
        self, test_client: AsyncClient, sample_user, _mock_redis
    ):
        """Failed job → 200 with error field populated."""
        token = _create_token(sample_user.id)
        job_id = str(uuid.uuid4())

        _mock_redis.hgetall.return_value = {
            "status": "failed",
            "progress": "40",
            "error": "Parse error: invalid CSV column",
            "created_at": "2026-03-05T12:00:00+05:30",
        }

        resp = await test_client.get(
            self.ENDPOINT.format(job_id=job_id),
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "failed"
        assert "Parse error" in body["error"]

    async def test_no_auth_returns_403(self, test_client: AsyncClient, _mock_redis):
        """No token → 401."""
        resp = await test_client.get(
            self.ENDPOINT.format(job_id=str(uuid.uuid4())),
        )
        assert resp.status_code == 401
