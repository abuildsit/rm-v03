from enum import Enum
from typing import Set

from prisma.enums import OrganizationRole


class Permission(Enum):
    """
    Defines all permissions available in the system.

    Permissions should follow the pattern: ACTION_RESOURCE
    Common actions: VIEW, MANAGE, DELETE, CREATE
    """

    # Organization permissions
    VIEW_MEMBERS = "view_members"  # View organization member list and details
    MANAGE_MEMBERS = "manage_members"  # Add, remove, update member roles
    MANAGE_BILLING = "manage_billing"  # Update billing settings and payment methods
    EDIT_ORGANIZATION = "edit_organization"  # Update organization profile and settings

    # Bank account permissions
    VIEW_BANK_ACCOUNTS = "view_bank_accounts"  # View bank account details
    MANAGE_BANK_ACCOUNTS = "manage_bank_accounts"  # Update bank account settings


ROLE_PERMISSIONS: dict[OrganizationRole, Set[Permission]] = {
    OrganizationRole.owner: {
        # Owners have all permissions
        Permission.VIEW_MEMBERS,
        Permission.MANAGE_MEMBERS,
        Permission.MANAGE_BILLING,
        Permission.EDIT_ORGANIZATION,
        Permission.VIEW_BANK_ACCOUNTS,
        Permission.MANAGE_BANK_ACCOUNTS,
    },
    OrganizationRole.admin: {
        # Admins have everything except billing management
        Permission.VIEW_MEMBERS,
        Permission.MANAGE_MEMBERS,
        Permission.EDIT_ORGANIZATION,
        Permission.VIEW_BANK_ACCOUNTS,
        Permission.MANAGE_BANK_ACCOUNTS,
    },
    OrganizationRole.auditor: {
        # Auditors have read-only access
        Permission.VIEW_MEMBERS,
        Permission.VIEW_BANK_ACCOUNTS,
    },
    OrganizationRole.user: {
        # Basic users can view bank accounts for transparency
        Permission.VIEW_BANK_ACCOUNTS,
    },
}
