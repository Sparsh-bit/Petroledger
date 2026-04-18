"""PetroLedger — FastAPI Dependency Re-exports."""

from app.api.deps.auth import get_current_active_user, get_current_user
from app.api.deps.rbac import require_role
from app.api.deps.tenant import get_current_tenant

__all__ = [
    "get_current_user",
    "get_current_active_user",
    "get_current_tenant",
    "require_role",
]
