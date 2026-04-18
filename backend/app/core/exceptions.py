"""
PetroLedger — Custom Exception Classes.

All domain-specific exceptions inherit from :class:`PetroLedgerError`
so they can be caught uniformly in FastAPI exception handlers.
"""

from __future__ import annotations

from typing import Any


class PetroLedgerError(Exception):
    """Base exception for the PetroLedger application."""

    default_message: str = "An unexpected error occurred."
    status_code: int = 500

    def __init__(
        self,
        message: str | None = None,
        *,
        detail: Any = None,
    ) -> None:
        self.message = message or self.default_message
        self.detail = detail
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        """Serialise the error for JSON responses."""
        payload: dict[str, Any] = {
            "error": self.__class__.__name__,
            "message": self.message,
        }
        if self.detail is not None:
            payload["detail"] = self.detail
        return payload


class AuthenticationError(PetroLedgerError):
    """Raised when authentication fails (invalid credentials, expired token, etc.)."""

    default_message = "Authentication failed."
    status_code = 401


class AuthorizationError(PetroLedgerError):
    """Raised when the user lacks permission for the requested action."""

    default_message = "You do not have permission to perform this action."
    status_code = 403


class NotFoundError(PetroLedgerError):
    """Raised when a requested resource cannot be found."""

    default_message = "The requested resource was not found."
    status_code = 404

    def __init__(
        self,
        resource: str | None = None,
        identifier: Any = None,
        **kwargs: Any,
    ) -> None:
        message = kwargs.pop("message", None)
        if message is None and resource:
            message = (
                f"{resource} with id '{identifier}' not found"
                if identifier is not None
                else f"{resource} not found"
            )
        super().__init__(message, **kwargs)


class ValidationError(PetroLedgerError):
    """Raised when domain-level validation fails (beyond Pydantic schema checks)."""

    default_message = "Validation failed."
    status_code = 422


class DuplicateError(PetroLedgerError):
    """Raised when a unique-constraint or business-rule duplicate is detected."""

    default_message = "A resource with the given identifier already exists."
    status_code = 409


class ReconciliationError(PetroLedgerError):
    """Raised when the reconciliation process encounters an unrecoverable issue."""

    default_message = "Reconciliation could not be completed."
    status_code = 422
