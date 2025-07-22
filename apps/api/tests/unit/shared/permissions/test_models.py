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

        # Remittance permissions
        assert Permission.VIEW_REMITTANCES.value == "view_remittances"
        assert Permission.CREATE_REMITTANCES.value == "create_remittances"
        assert Permission.MANAGE_REMITTANCES.value == "manage_remittances"
        assert Permission.APPROVE_REMITTANCES.value == "approve_remittances"

    def test_permission_enum_structure(self):
        """Test permission enum structure and naming conventions."""
        all_permissions = {p.name for p in Permission}

        # Test reasonable number of permissions (prevents accidental deletions)
        assert len(all_permissions) >= 10, "Should have at least 10 permissions defined"

        # Test naming conventions - all permissions should be UPPERCASE with underscores
        for perm_name in all_permissions:
            assert perm_name.isupper(), f"Permission {perm_name} should be uppercase"
            assert (
                "_" in perm_name
            ), f"Permission {perm_name} should use underscore naming"

        # Test that core business domain permissions exist
        core_domains = [
            "MEMBERS",
            "BANK_ACCOUNTS",
            "INTEGRATIONS",
            "INVOICES",
            "REMITTANCES",
        ]
        for domain in core_domains:
            view_perm = f"VIEW_{domain}"
            assert any(
                view_perm in p.name for p in Permission
            ), f"Should have VIEW permission for {domain}"

        # Test that permission values follow snake_case convention
        for perm in Permission:
            assert (
                perm.value.islower()
            ), f"Permission value {perm.value} should be lowercase"
            assert (
                "_" in perm.value
            ), f"Permission value {perm.value} should use snake_case"


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
        assert Permission.VIEW_REMITTANCES in owner_permissions
        assert Permission.CREATE_REMITTANCES in owner_permissions
        assert Permission.MANAGE_REMITTANCES in owner_permissions
        assert Permission.APPROVE_REMITTANCES in owner_permissions

    def test_admin_permissions(self):
        """Test that admins have most permissions except billing."""
        admin_permissions = ROLE_PERMISSIONS[OrganizationRole.admin]
        owner_permissions = ROLE_PERMISSIONS[OrganizationRole.owner]

        # Admin should have most permissions but not billing
        assert Permission.MANAGE_BILLING not in admin_permissions
        assert Permission.MANAGE_BILLING in owner_permissions

        # Admin should have substantial permissions (at least 10)
        assert len(admin_permissions) >= 10, "Admin should have substantial permissions"

        # Admin should be a subset of owner permissions (minus billing)
        admin_plus_billing = admin_permissions | {Permission.MANAGE_BILLING}
        assert admin_plus_billing.issubset(
            owner_permissions
        ), "Admin permissions should be subset of owner (plus billing)"

    def test_auditor_permissions(self):
        """Test that auditors have read-only permissions."""
        auditor_permissions = ROLE_PERMISSIONS[OrganizationRole.auditor]

        # Auditors should have view permissions for key domains
        auditor_view_permissions = [
            p for p in auditor_permissions if p.name.startswith("VIEW_")
        ]

        # Should have substantial view access
        assert (
            len(auditor_view_permissions) >= 4
        ), "Auditor should have view access to key domains"

        # Should NOT have any management, create, or modify permissions
        forbidden_actions = ["MANAGE_", "CREATE_", "EDIT_", "SYNC_", "APPROVE_"]
        for perm in auditor_permissions:
            for action in forbidden_actions:
                assert not perm.name.startswith(
                    action
                ), f"Auditor should not have {action} permission: {perm.name}"

    def test_user_permissions(self):
        """Test that basic users have minimal but functional permissions."""
        user_permissions = ROLE_PERMISSIONS[OrganizationRole.user]

        # Users should have basic access but limited permissions
        assert len(user_permissions) >= 2, "User should have some basic permissions"
        assert len(user_permissions) <= 5, "User should have limited permissions"

        # Users should be able to view bank accounts for transparency
        assert Permission.VIEW_BANK_ACCOUNTS in user_permissions

        # Users should NOT have administrative permissions
        admin_permissions = [
            "MANAGE_MEMBERS",
            "MANAGE_BILLING",
            "EDIT_ORGANIZATION",
            "MANAGE_BANK_ACCOUNTS",
        ]
        for admin_perm_name in admin_permissions:
            admin_perm = next(
                (p for p in Permission if p.name == admin_perm_name), None
            )
            if admin_perm:
                assert (
                    admin_perm not in user_permissions
                ), f"User should not have {admin_perm_name}"

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
        # Note: user permissions are not a subset of auditor permissions by design
        # (user has CREATE_REMITTANCES but auditor is read-only)

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
