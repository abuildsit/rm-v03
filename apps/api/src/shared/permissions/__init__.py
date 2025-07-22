"""
Shared permission system for role-based access control.

This module provides a centralized permission system that can be used
across all domains in the application.

Usage:
    from src.shared.permissions import Permission, require_permission

    @router.get("/{org_id}/resource")
    async def get_resource(
        membership: OrganizationMember = Depends(
            require_permission(Permission.VIEW_RESOURCE)
        )
    ):
        pass
"""

from .dependencies import require_permission
from .models import ROLE_PERMISSIONS, Permission
from .services import has_permission

__all__ = [
    "Permission",
    "ROLE_PERMISSIONS",
    "has_permission",
    "require_permission",
]
