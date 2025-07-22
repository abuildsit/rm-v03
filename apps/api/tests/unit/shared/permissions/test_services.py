"""
Tests for shared permissions services (has_permission function).
"""

import pytest
from prisma.enums import OrganizationRole

from src.shared.permissions.models import Permission
from src.shared.permissions.services import has_permission


class TestHasPermission:
    """Test the has_permission function."""

    def test_owner_has_all_permissions(self):
        """Test that owners have all permissions."""
        role = OrganizationRole.owner

        # Test all permissions
        assert has_permission(role, Permission.VIEW_MEMBERS) is True
        assert has_permission(role, Permission.MANAGE_MEMBERS) is True
        assert has_permission(role, Permission.MANAGE_BILLING) is True
        assert has_permission(role, Permission.EDIT_ORGANIZATION) is True
        assert has_permission(role, Permission.VIEW_BANK_ACCOUNTS) is True
        assert has_permission(role, Permission.MANAGE_BANK_ACCOUNTS) is True

    def test_admin_permissions(self):
        """Test admin permissions (everything except billing)."""
        role = OrganizationRole.admin

        # Should have these permissions
        assert has_permission(role, Permission.VIEW_MEMBERS) is True
        assert has_permission(role, Permission.MANAGE_MEMBERS) is True
        assert has_permission(role, Permission.EDIT_ORGANIZATION) is True
        assert has_permission(role, Permission.VIEW_BANK_ACCOUNTS) is True
        assert has_permission(role, Permission.MANAGE_BANK_ACCOUNTS) is True

        # Should NOT have billing permission
        assert has_permission(role, Permission.MANAGE_BILLING) is False

    def test_auditor_permissions(self):
        """Test auditor permissions (read-only)."""
        role = OrganizationRole.auditor

        # Should have these read permissions
        assert has_permission(role, Permission.VIEW_MEMBERS) is True
        assert has_permission(role, Permission.VIEW_BANK_ACCOUNTS) is True

        # Should NOT have these management permissions
        assert has_permission(role, Permission.MANAGE_MEMBERS) is False
        assert has_permission(role, Permission.MANAGE_BILLING) is False
        assert has_permission(role, Permission.EDIT_ORGANIZATION) is False
        assert has_permission(role, Permission.MANAGE_BANK_ACCOUNTS) is False

    def test_user_permissions(self):
        """Test user permissions (minimal access)."""
        role = OrganizationRole.user

        # Should have bank account view permission
        assert has_permission(role, Permission.VIEW_BANK_ACCOUNTS) is True

        # Should NOT have any other permissions
        assert has_permission(role, Permission.VIEW_MEMBERS) is False
        assert has_permission(role, Permission.MANAGE_MEMBERS) is False
        assert has_permission(role, Permission.MANAGE_BILLING) is False
        assert has_permission(role, Permission.EDIT_ORGANIZATION) is False
        assert has_permission(role, Permission.MANAGE_BANK_ACCOUNTS) is False

    def test_all_role_permission_combinations(self):
        """Test all possible role-permission combinations systematically."""
        test_cases = [
            # (role, permission, expected_result)
            (OrganizationRole.owner, Permission.VIEW_MEMBERS, True),
            (OrganizationRole.owner, Permission.MANAGE_MEMBERS, True),
            (OrganizationRole.owner, Permission.MANAGE_BILLING, True),
            (OrganizationRole.owner, Permission.EDIT_ORGANIZATION, True),
            (OrganizationRole.owner, Permission.VIEW_BANK_ACCOUNTS, True),
            (OrganizationRole.owner, Permission.MANAGE_BANK_ACCOUNTS, True),
            (OrganizationRole.admin, Permission.VIEW_MEMBERS, True),
            (OrganizationRole.admin, Permission.MANAGE_MEMBERS, True),
            (OrganizationRole.admin, Permission.MANAGE_BILLING, False),
            (OrganizationRole.admin, Permission.EDIT_ORGANIZATION, True),
            (OrganizationRole.admin, Permission.VIEW_BANK_ACCOUNTS, True),
            (OrganizationRole.admin, Permission.MANAGE_BANK_ACCOUNTS, True),
            (OrganizationRole.auditor, Permission.VIEW_MEMBERS, True),
            (OrganizationRole.auditor, Permission.MANAGE_MEMBERS, False),
            (OrganizationRole.auditor, Permission.MANAGE_BILLING, False),
            (OrganizationRole.auditor, Permission.EDIT_ORGANIZATION, False),
            (OrganizationRole.auditor, Permission.VIEW_BANK_ACCOUNTS, True),
            (OrganizationRole.auditor, Permission.MANAGE_BANK_ACCOUNTS, False),
            (OrganizationRole.user, Permission.VIEW_MEMBERS, False),
            (OrganizationRole.user, Permission.MANAGE_MEMBERS, False),
            (OrganizationRole.user, Permission.MANAGE_BILLING, False),
            (OrganizationRole.user, Permission.EDIT_ORGANIZATION, False),
            (OrganizationRole.user, Permission.VIEW_BANK_ACCOUNTS, True),
            (OrganizationRole.user, Permission.MANAGE_BANK_ACCOUNTS, False),
        ]

        for role, permission, expected in test_cases:
            result = has_permission(role, permission)
            assert result == expected, (
                f"Expected {role.value} to {'have' if expected else 'not have'} "
                f"{permission.value}"
            )

    @pytest.mark.parametrize(
        "role",
        [
            OrganizationRole.owner,
            OrganizationRole.admin,
            OrganizationRole.auditor,
            OrganizationRole.user,
        ],
    )
    def test_has_permission_with_all_roles(self, role):
        """Test has_permission function doesn't crash with any valid role."""
        # This test ensures the function handles all roles gracefully
        for permission in Permission:
            result = has_permission(role, permission)
            assert isinstance(result, bool), (
                f"has_permission should return bool for {role.value} and "
                f"{permission.value}"
            )

    def test_has_permission_returns_boolean(self):
        """Test that has_permission always returns a boolean."""
        # Test a few combinations to ensure boolean return
        assert isinstance(
            has_permission(OrganizationRole.owner, Permission.VIEW_MEMBERS), bool
        )
        assert isinstance(
            has_permission(OrganizationRole.user, Permission.MANAGE_BILLING), bool
        )
        assert isinstance(
            has_permission(OrganizationRole.auditor, Permission.VIEW_BANK_ACCOUNTS),
            bool,
        )

    def test_bank_account_permissions_specifically(self):
        """Test bank account permissions across all roles."""
        # VIEW_BANK_ACCOUNTS should be available to all roles
        assert (
            has_permission(OrganizationRole.owner, Permission.VIEW_BANK_ACCOUNTS)
            is True
        )
        assert (
            has_permission(OrganizationRole.admin, Permission.VIEW_BANK_ACCOUNTS)
            is True
        )
        assert (
            has_permission(OrganizationRole.auditor, Permission.VIEW_BANK_ACCOUNTS)
            is True
        )
        assert (
            has_permission(OrganizationRole.user, Permission.VIEW_BANK_ACCOUNTS) is True
        )

        # MANAGE_BANK_ACCOUNTS should only be available to owner and admin
        assert (
            has_permission(OrganizationRole.owner, Permission.MANAGE_BANK_ACCOUNTS)
            is True
        )
        assert (
            has_permission(OrganizationRole.admin, Permission.MANAGE_BANK_ACCOUNTS)
            is True
        )
        assert (
            has_permission(OrganizationRole.auditor, Permission.MANAGE_BANK_ACCOUNTS)
            is False
        )
        assert (
            has_permission(OrganizationRole.user, Permission.MANAGE_BANK_ACCOUNTS)
            is False
        )
