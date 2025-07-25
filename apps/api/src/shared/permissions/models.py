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

    # Integration permissions
    VIEW_INTEGRATIONS = "view_integrations"  # View integration connection status
    MANAGE_INTEGRATIONS = "manage_integrations"  # Connect/disconnect integrations

    # Invoice permissions
    VIEW_INVOICES = "view_invoices"  # View invoice list and details
    SYNC_INVOICES = "sync_invoices"  # Trigger invoice synchronization

    # Payment permissions (for future use)
    CREATE_PAYMENTS = "create_payments"  # Create payments in accounting system

    # Remittance permissions
    VIEW_REMITTANCES = "view_remittances"  # View remittance list and details
    CREATE_REMITTANCES = "create_remittances"  # Upload new remittances
    MANAGE_REMITTANCES = "manage_remittances"  # Update remittance details
    APPROVE_REMITTANCES = "approve_remittances"  # Approve remittance matches


ROLE_PERMISSIONS: dict[OrganizationRole, Set[Permission]] = {
    OrganizationRole.owner: {
        # Owners have all permissions
        Permission.VIEW_MEMBERS,
        Permission.MANAGE_MEMBERS,
        Permission.MANAGE_BILLING,
        Permission.EDIT_ORGANIZATION,
        Permission.VIEW_BANK_ACCOUNTS,
        Permission.MANAGE_BANK_ACCOUNTS,
        Permission.VIEW_INTEGRATIONS,
        Permission.MANAGE_INTEGRATIONS,
        Permission.VIEW_INVOICES,
        Permission.SYNC_INVOICES,
        Permission.CREATE_PAYMENTS,
        Permission.VIEW_REMITTANCES,
        Permission.CREATE_REMITTANCES,
        Permission.MANAGE_REMITTANCES,
        Permission.APPROVE_REMITTANCES,
    },
    OrganizationRole.admin: {
        # Admins have everything except billing management
        Permission.VIEW_MEMBERS,
        Permission.MANAGE_MEMBERS,
        Permission.EDIT_ORGANIZATION,
        Permission.VIEW_BANK_ACCOUNTS,
        Permission.MANAGE_BANK_ACCOUNTS,
        Permission.VIEW_INTEGRATIONS,
        Permission.MANAGE_INTEGRATIONS,
        Permission.VIEW_INVOICES,
        Permission.SYNC_INVOICES,
        Permission.CREATE_PAYMENTS,
        Permission.VIEW_REMITTANCES,
        Permission.CREATE_REMITTANCES,
        Permission.MANAGE_REMITTANCES,
        Permission.APPROVE_REMITTANCES,
    },
    OrganizationRole.auditor: {
        # Auditors have read-only access
        Permission.VIEW_MEMBERS,
        Permission.VIEW_BANK_ACCOUNTS,
        Permission.VIEW_INTEGRATIONS,
        Permission.VIEW_INVOICES,
        Permission.VIEW_REMITTANCES,
    },
    OrganizationRole.user: {
        # Basic users can view bank accounts and basic remittance operations
        Permission.VIEW_BANK_ACCOUNTS,
        Permission.VIEW_REMITTANCES,
        Permission.CREATE_REMITTANCES,
    },
}
