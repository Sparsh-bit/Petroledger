"""
PetroLedger — Audit Service.

Provides a high-level API for recording and querying immutable
audit-trail entries.  Every significant data mutation (e.g. file
upload, reconciliation override, shift completion) should be logged
through this service.
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog

logger = structlog.stdlib.get_logger("petroledger.services.audit")


class AuditService:
    """
    Immutable audit-trail logger.

    Usage::

        audit = AuditService()
        await audit.log(
            db, action="upi_upload", entity_type="shift",
            entity_id=shift.id, user_id=user.id, org_id=org.id,
            before=None, after={"count": 42},
        )
    """

    # ── Write ───────────────────────────────────────────────────────

    @staticmethod
    async def log(
        db: AsyncSession,
        *,
        action: str,
        entity_type: str,
        entity_id: uuid.UUID,
        user_id: uuid.UUID,
        org_id: uuid.UUID,
        tenant_id: uuid.UUID,
        before: dict[str, Any] | None = None,
        after: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        ip_address: str | None = None,
    ) -> None:
        """
        Record an audit-trail entry.

        Parameters
        ----------
        db:
            Async database session (caller is responsible for commit).
        action:
            Verb describing the mutation, e.g. ``"upi_upload"``,
            ``"reconciliation_override"``, ``"shift_complete"``.
        entity_type:
            Kind of entity being changed, e.g. ``"shift"``,
            ``"transaction"``, ``"reconciliation"``.
        entity_id:
            Primary key of the entity.
        user_id:
            Who performed the action.
        org_id:
            Organisation scope.
        before:
            Serialised state *before* the change (``None`` for creates).
        after:
            Serialised state *after* the change (``None`` for deletes).
        metadata:
            Additional context (filename, IP, source system, etc.).
        """
        entry = AuditLog(
            id=uuid.uuid4(),
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            user_id=user_id,
            org_id=org_id,
            tenant_id=tenant_id,
            before_state=before,
            after_state=after,
            metadata_=metadata,
            ip_address=ip_address,
        )
        db.add(entry)
        await db.flush()

        logger.info(
            "audit_logged",
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id),
            user_id=str(user_id),
            org_id=str(org_id),
        )

    # ── Convenience ─────────────────────────────────────────────────

    @staticmethod
    async def log_event(
        db: AsyncSession,
        *,
        user: "object",            # app.models.user.User — quoted to avoid cycle
        action: str,
        entity_type: str,
        entity_id: uuid.UUID,
        org_id: uuid.UUID | None = None,
        before: dict[str, Any] | None = None,
        after: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        request: "object | None" = None,   # fastapi.Request
    ) -> None:
        """Log an event scoped to the acting user's tenant and request IP.

        Resolves:
          - tenant_id from `user.tenant_id`
          - org_id from `user.org_id` if not explicitly provided (falls back to
            the passed value — required for owner-level actions without an org)
          - ip_address from `request.client.host` when available
        """
        resolved_org = org_id if org_id is not None else getattr(user, "org_id", None)
        if resolved_org is None:
            raise ValueError("log_event requires an org_id (pass one or use a user with org_id set)")

        ip = None
        if request is not None:
            client = getattr(request, "client", None)
            if client is not None:
                ip = getattr(client, "host", None)

        await AuditService.log(
            db,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            user_id=getattr(user, "id"),
            org_id=resolved_org,
            tenant_id=getattr(user, "tenant_id"),
            before=before,
            after=after,
            metadata=metadata,
            ip_address=ip,
        )

    # ── Read ────────────────────────────────────────────────────────

    @staticmethod
    async def get_audit_trail(
        db: AsyncSession,
        entity_type: str,
        entity_id: uuid.UUID,
        org_id: uuid.UUID,
    ) -> list[AuditLog]:
        """
        Retrieve the full audit trail for a specific entity,
        ordered newest-first.

        Parameters
        ----------
        db:
            Async database session.
        entity_type:
            Entity kind filter (e.g. ``"shift"``).
        entity_id:
            Primary key of the entity.
        org_id:
            Organisation scope (ensures cross-org isolation).

        Returns
        -------
        list[AuditLog]
            Chronologically descending list of audit entries.
        """
        stmt = (
            select(AuditLog)
            .where(
                AuditLog.entity_type == entity_type,
                AuditLog.entity_id == entity_id,
                AuditLog.org_id == org_id,
            )
            .order_by(AuditLog.created_at.desc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())
