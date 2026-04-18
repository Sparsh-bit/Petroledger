"""
PetroLedger — S3 Storage Service.

Thin wrapper around boto3 for uploading, downloading, and deleting
objects from the configured S3 bucket.
"""

from __future__ import annotations

import asyncio
from contextlib import suppress

import boto3
from botocore.exceptions import ClientError

from app.core.config import get_settings


class S3Service:
    def __init__(self) -> None:
        s = get_settings()
        self._client = boto3.client(
            "s3",
            region_name=s.AWS_REGION,
            **(
                {
                    "aws_access_key_id": s.AWS_ACCESS_KEY_ID,
                    "aws_secret_access_key": s.AWS_SECRET_ACCESS_KEY,
                }
                if s.AWS_ACCESS_KEY_ID
                else {}
            ),
        )
        self._bucket = s.S3_BUCKET

    def upload_file(self, file_bytes: bytes, key: str) -> str:
        """Upload bytes to S3 under *key*. Returns the key. (sync, for Celery)"""
        self._client.put_object(Bucket=self._bucket, Key=key, Body=file_bytes)
        return key

    def download_file(self, key: str) -> bytes:
        """Download object at *key* and return its raw bytes. (sync, for Celery)"""
        resp = self._client.get_object(Bucket=self._bucket, Key=key)
        return resp["Body"].read()

    def get_presigned_url(self, key: str, expires_in: int = 3600) -> str:
        """Return a pre-signed GET URL valid for *expires_in* seconds."""
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=expires_in,
        )

    def delete_file(self, key: str) -> None:
        """Delete object at *key*. Silently ignores missing objects. (sync, for Celery)"""
        with suppress(ClientError):
            self._client.delete_object(Bucket=self._bucket, Key=key)

    # ── Async variants for use inside FastAPI request handlers ─────────

    async def upload_file_async(self, file_bytes: bytes, key: str) -> str:
        """Upload bytes without blocking the event loop."""
        return await asyncio.to_thread(self.upload_file, file_bytes, key)

    async def download_file_async(self, key: str) -> bytes:
        """Download bytes without blocking the event loop."""
        return await asyncio.to_thread(self.download_file, key)

    async def delete_file_async(self, key: str) -> None:
        """Delete without blocking the event loop."""
        await asyncio.to_thread(self.delete_file, key)

    async def get_presigned_url_async(
        self, key: str, expires_in: int = 3600
    ) -> str:
        """Generate a presigned URL without blocking the event loop."""
        return await asyncio.to_thread(self.get_presigned_url, key, expires_in)