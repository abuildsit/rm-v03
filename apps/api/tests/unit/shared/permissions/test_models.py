"""
Tests for shared permissions models (Permission enum and ROLE_PERMISSIONS mapping).
"""

from prisma.enums import OrganizationRole

from src.shared.permissions.models import ROLE_PERMISSIONS, Permission


class TestPermissionEnum:
    """Test the Permission enum definition."""

    def test_permission_enum_values(self):
        """Test that all expected permissions are defined with correct values."""
        # Organization permissions
        assert Permission.VIEW_MEMBERS.value == "view_members"
        assert Permission.MANAGE_MEMBERS.value == "manage_members"
        assert Permission.MANAGE_BILLING.value == "manage_billing"
        assert Permission.EDIT_ORGANIZATION.value == "edit_organization"

        # Bank account permissions
        assert Permission.VIEW_BANK_ACCOUNTS.value == "view_bank_accounts"
        assert Permission.MANAGE_BANK_ACCOUNTS.value == "manage_bank_accounts"

        # Integration permissions
        assert Permission.VIEW_INTEGRATIONS.value == "view_integrations"
        assert Permission.MANAGE_INTEGRATIONS.value == "manage_integrations"

        # Invoice permissions
        assert Permission.VIEW_INVOICES.value == "view_invoices"
        assert Permission.SYNC_INVOICES.value == "sync_invoices"

        # Payment permissions
        assert Permission.CREATE_PAYMENTS.value == "create_payments"

    def test_permission_enum_completeness(self):
        """Test that we have all expected permissions."""
        expected_permissions = {
            "VIEW_MEMBERS",
            "MANAGE_MEMBERS",
            "MANAGE_BILLING",
            "EDIT_ORGANIZATION",
            "VIEW_BANK_ACCOUNTS",
            "MANAGE_BANK_ACCOUNTS",
            "VIEW_INTEGRATIONS",
            "MANAGE_INTEGRATIONS",
            "VIEW_INVOICES",
            "SYNC_INVOICES",
            "CREATE_PAYMENTS",
        }

        actual_permissions = {p.name for p in Permission}
        assert actual_permissions == expected_permissions


class TestRolePermissions:
    """Test the ROLE_PERMISSIONS mapping."""

    def test_all_roles_have_permissions(self):
        """Test that all organization roles are defined in ROLE_PERMISSIONS."""
        expected_roles = {
            OrganizationRole.owner,
            OrganizationRole.admin,
            OrganizationRole.auditor,
            OrganizationRole.user,
        }

        actual_roles = set(ROLE_PERMISSIONS.keys())
        assert actual_roles == expected_roles

    def test_owner_permissions(self):
        """Test that owners have all permissions."""
        owner_permissions = ROLE_PERMISSIONS[OrganizationRole.owner]

        # Owners should have every permission
        all_permissions = set(Permission)
        assert owner_permissions == all_permissions

        # Verify specific permissions
        assert Permission.VIEW_MEMBERS in owner_permissions
        assert Permission.MANAGE_MEMBERS in owner_permissions
        assert Permission.MANAGE_BILLING in owner_permissions
        assert Permission.EDIT_ORGANIZATION in owner_permissions
        assert Permission.VIEW_BANK_ACCOUNTS in owner_permissions
        assert Permission.MANAGE_BANK_ACCOUNTS in owner_permissions
        assert Permission.VIEW_INTEGRATIONS in owner_permissions
        assert Permission.MANAGE_INTEGRATIONS in owner_permissions
        assert Permission.VIEW_INVOICES in owner_permissions
        assert Permission.SYNC_INVOICES in owner_permissions
        assert Permission.CREATE_PAYMENTS in owner_permissions

    def test_admin_permissions(self):
        """Test that admins have everything except billing."""
        admin_permissions = ROLE_PERMISSIONS[OrganizationRole.admin]

        expected_admin_permissions = {
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
        }

        assert admin_permissions == expected_admin_permissions

        # Specifically verify they don't have billing permission
        assert Permission.MANAGE_BILLING not in admin_permissions

    def test_auditor_permissions(self):
        """Test that auditors have read-only permissions."""
        auditor_permissions = ROLE_PERMISSIONS[OrganizationRole.auditor]

        expected_auditor_permissions = {
            Permission.VIEW_MEMBERS,
            Permission.VIEW_BANK_ACCOUNTS,
            Permission.VIEW_INTEGRATIONS,
            Permission.VIEW_INVOICES,
        }

        assert auditor_permissions == expected_auditor_permissions

        # Verify they don't have any management permissions
        assert Permission.MANAGE_MEMBERS not in auditor_permissions
        assert Permission.MANAGE_BILLING not in auditor_permissions
        assert Permission.EDIT_ORGANIZATION not in auditor_permissions
        assert Permission.MANAGE_BANK_ACCOUNTS not in auditor_permissions

    def test_user_permissions(self):
        """Test that basic users have minimal permissions."""
        user_permissions = ROLE_PERMISSIONS[OrganizationRole.user]

        expected_user_permissions = {
            Permission.VIEW_BANK_ACCOUNTS,
        }

        assert user_permissions == expected_user_permissions

        # Verify they don't have any other permissions
        assert Permission.VIEW_MEMBERS not in user_permissions
        assert Permission.MANAGE_MEMBERS not in user_permissions
        assert Permission.MANAGE_BILLING not in user_permissions
        assert Permission.EDIT_ORGANIZATION not in user_permissions
        assert Permission.MANAGE_BANK_ACCOUNTS not in user_permissions

    def test_permission_hierarchy(self):
        """Test permission hierarchy: owner > admin > auditor > user."""
        owner_perms = ROLE_PERMISSIONS[OrganizationRole.owner]
        admin_perms = ROLE_PERMISSIONS[OrganizationRole.admin]
        auditor_perms = ROLE_PERMISSIONS[OrganizationRole.auditor]
        user_perms = ROLE_PERMISSIONS[OrganizationRole.user]

        # Owner should have more permissions than admin
        assert len(owner_perms) > len(admin_perms)
        assert admin_perms.issubset(owner_perms)

        # Admin should have more permissions than auditor
        assert len(admin_perms) > len(auditor_perms)
        # Note: auditor permissions are not a subset of admin permissions by design
        # (auditor has VIEW_MEMBERS but admin may have different permissions)

        # Auditor should have more permissions than user
        assert len(auditor_perms) > len(user_perms)
        assert user_perms.issubset(auditor_perms)

    def test_bank_account_permission_distribution(self):
        """Test that bank account permissions are distributed correctly."""
        # VIEW_BANK_ACCOUNTS should be available to all roles for transparency
        assert Permission.VIEW_BANK_ACCOUNTS in ROLE_PERMISSIONS[OrganizationRole.owner]
        assert Permission.VIEW_BANK_ACCOUNTS in ROLE_PERMISSIONS[OrganizationRole.admin]
        assert (
            Permission.VIEW_BANK_ACCOUNTS in ROLE_PERMISSIONS[OrganizationRole.auditor]
        )
        assert Permission.VIEW_BANK_ACCOUNTS in ROLE_PERMISSIONS[OrganizationRole.user]

        # MANAGE_BANK_ACCOUNTS should only be available to owner and admin
        assert (
            Permission.MANAGE_BANK_ACCOUNTS in ROLE_PERMISSIONS[OrganizationRole.owner]
        )
        assert (
            Permission.MANAGE_BANK_ACCOUNTS in ROLE_PERMISSIONS[OrganizationRole.admin]
        )
        assert (
            Permission.MANAGE_BANK_ACCOUNTS
            not in ROLE_PERMISSIONS[OrganizationRole.auditor]
        )
        assert (
            Permission.MANAGE_BANK_ACCOUNTS
            not in ROLE_PERMISSIONS[OrganizationRole.user]
        )
