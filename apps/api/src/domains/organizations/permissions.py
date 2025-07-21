# apps/api/src/domains/organizations/permissions.py
from enum import Enum
from typing import Set

from prisma.enums import OrganizationRole


class Permission(Enum):
    VIEW_MEMBERS = "view_members"
    INVITE_MEMBERS = "invite_members"
    REMOVE_MEMBERS = "remove_members"
    MANAGE_BILLING = "manage_billing"
    EDIT_ORGANIZATION = "edit_organization"


ROLE_PERMISSIONS: dict[OrganizationRole, Set[Permission]] = {
    OrganizationRole.owner: {
        Permission.VIEW_MEMBERS,
        Permission.INVITE_MEMBERS,
        Permission.REMOVE_MEMBERS,
        Permission.MANAGE_BILLING,
        Permission.EDIT_ORGANIZATION,
    },
    OrganizationRole.admin: {
        Permission.VIEW_MEMBERS,
        Permission.INVITE_MEMBERS,
        Permission.REMOVE_MEMBERS,
        Permission.EDIT_ORGANIZATION,
    },
    OrganizationRole.auditor: {
        Permission.VIEW_MEMBERS,
    },
    OrganizationRole.user: set(),
}


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
