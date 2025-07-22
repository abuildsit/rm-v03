from prisma.enums import OrganizationRole

from .models import ROLE_PERMISSIONS, Permission


def has_permission(role: OrganizationRole, permission: Permission) -> bool:
    """
    Check if a role has a specific permission.

    Args:
        role: The organization role to check
        permission: The permission to validate

    Returns:
        True if the role has the permission, False otherwise
    """
    return permission in ROLE_PERMISSIONS.get(role, set())
