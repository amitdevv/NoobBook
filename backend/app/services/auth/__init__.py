"""
Auth services package.
"""

from app.services.auth.rbac import (
    get_request_identity,
    require_admin,
    require_auth,
    require_permission,
    is_auth_required,
)
from app.services.auth.permissions import (
    get_user_permissions,
    update_user_permissions,
    user_has_permission,
    DEFAULT_PERMISSIONS,
)

__all__ = [
    "get_request_identity",
    "require_admin",
    "require_auth",
    "require_permission",
    "is_auth_required",
    "get_user_permissions",
    "update_user_permissions",
    "user_has_permission",
    "DEFAULT_PERMISSIONS",
]

