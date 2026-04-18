"""PetroLedger — Hashing Utilities.

Deterministic content hashing used for deduplication and idempotency
checks across data-ingestion and reconciliation pipelines.
"""

from __future__ import annotations

import hashlib


def sha256_hex(data: str) -> str:
    """Return the hex-encoded SHA-256 digest of *data* (UTF-8 encoded)."""
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def generate_idempotency_key(*parts: str) -> str:
    """Build a deterministic idempotency key by joining *parts* with ``|``
    and returning the SHA-256 hex digest.

    Example::

        generate_idempotency_key("shift-abc", "upi", "2026-03-05")
        # → "e3b0c44298fc1c149afb..."
    """
    return sha256_hex("|".join(parts))
