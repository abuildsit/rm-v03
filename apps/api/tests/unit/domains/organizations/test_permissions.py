"""
Tests for organization permissions system in src/domains/organizations/permissions.py

Tests the permission enumeration and role-based access control logic.
"""

import pytest
from prisma.enums import OrganizationRole

from src.shared.permissions import (
    ROLE_PERMISSIONS,
    Permission,
    has_permission,
)


class TestPermissionEnum:
    """Test Permission enumeration values and consistency."""

    def test_permission_enum_values(self):
        """Test that all expected permissions are defined."""
        expected_permissions = {
            "VIEW_MEMBERS",
            "MANAGE_MEMBERS",
            "MANAGE_BILLING",
            "EDIT_ORGANIZATION",
            "VIEW_BANK_ACCOUNTS",
            "MANAGE_BANK_ACCOUNTS",
        }

        actual_permissions = {permission.name for permission in Permission}
        assert actual_permissions == expected_permissions

    def test_permission_string_values(self):
        """Test that permission string values are correctly formatted."""
        assert Permission.VIEW_MEMBERS.value == "view_members"
        assert Permission.MANAGE_MEMBERS.value == "manage_members"
        assert Permission.MANAGE_BILLING.value == "manage_billing"
        assert Permission.EDIT_ORGANIZATION.value == "edit_organization"
        assert Permission.VIEW_BANK_ACCOUNTS.value == "view_bank_accounts"
        assert Permission.MANAGE_BANK_ACCOUNTS.value == "manage_bank_accounts"


class TestRolePermissions:
    """Test role-to-permission mapping configuration."""

    def test_owner_has_all_permissions(self):
        """Test that owner role has access to all permissions."""
        owner_permissions = ROLE_PERMISSIONS[OrganizationRole.owner]
        all_permissions = set(Permission)

        assert owner_permissions == all_permissions
        assert len(owner_permissions) == 6

    def test_admin_has_most_permissions_except_billing(self):
        """Test that admin role has most permissions except billing management."""
        admin_permissions = ROLE_PERMISSIONS[OrganizationRole.admin]
        expected_admin_permissions = {
            Permission.VIEW_MEMBERS,
            Permission.MANAGE_MEMBERS,
            Permission.EDIT_ORGANIZATION,
            Permission.VIEW_BANK_ACCOUNTS,
            Permission.MANAGE_BANK_ACCOUNTS,
        }

        assert admin_permissions == expected_admin_permissions
        assert Permission.MANAGE_BILLING not in admin_permissions
        assert len(admin_permissions) == 5

    def test_auditor_has_limited_permissions(self):
        """Test that auditor role has only view permissions."""
        auditor_permissions = ROLE_PERMISSIONS[OrganizationRole.auditor]
        expected_auditor_permissions = {
            Permission.VIEW_MEMBERS,
            Permission.VIEW_BANK_ACCOUNTS,
        }

        assert auditor_permissions == expected_auditor_permissions
        assert len(auditor_permissions) == 2

    def test_user_has_no_special_permissions(self):
        """Test that user role has minimal permissions."""
        user_permissions = ROLE_PERMISSIONS[OrganizationRole.user]
        expected_user_permissions = {
            Permission.VIEW_BANK_ACCOUNTS,
        }

        assert user_permissions == expected_user_permissions
        assert len(user_permissions) == 1

    def test_all_roles_defined_in_mapping(self):
        """Test that all organization roles are defined in permissions mapping."""
        expected_roles = {
            OrganizationRole.owner,
            OrganizationRole.admin,
            OrganizationRole.user,
            OrganizationRole.auditor,
        }

        actual_roles = set(ROLE_PERMISSIONS.keys())
        assert actual_roles == expected_roles


class TestHasPermissionFunction:
    """Test the has_permission utility function."""

    @pytest.mark.parametrize(
        "role,permission,expected",
        [
            # Owner tests - should have all permissions
            (OrganizationRole.owner, Permission.VIEW_MEMBERS, True),
            (OrganizationRole.owner, Permission.MANAGE_MEMBERS, True),
            (OrganizationRole.owner, Permission.MANAGE_BILLING, True),
            (OrganizationRole.owner, Permission.EDIT_ORGANIZATION, True),
            # Admin tests - should have most permissions except billing
            (OrganizationRole.admin, Permission.VIEW_MEMBERS, True),
            (OrganizationRole.admin, Permission.MANAGE_MEMBERS, True),
            (OrganizationRole.admin, Permission.MANAGE_BILLING, False),
            (OrganizationRole.admin, Permission.EDIT_ORGANIZATION, True),
            # Auditor tests - should only have view permission
            (OrganizationRole.auditor, Permission.VIEW_MEMBERS, True),
            (OrganizationRole.auditor, Permission.MANAGE_MEMBERS, False),
            (OrganizationRole.auditor, Permission.MANAGE_BILLING, False),
            (OrganizationRole.auditor, Permission.EDIT_ORGANIZATION, False),
            # User tests - should have no permissions
            (OrganizationRole.user, Permission.VIEW_MEMBERS, False),
            (OrganizationRole.user, Permission.MANAGE_MEMBERS, False),
            (OrganizationRole.user, Permission.MANAGE_BILLING, False),
            (OrganizationRole.user, Permission.EDIT_ORGANIZATION, False),
        ],
    )
    def test_has_permission_combinations(self, role, permission, expected):
        """Test all role and permission combinations."""
        result = has_permission(role, permission)
        assert result == expected

    def test_has_permission_with_nonexistent_role(self):
        """Test has_permission gracefully handles undefined roles."""

        # Create a mock role that doesn't exist in our mapping
        class MockRole:
            def __init__(self, value):
                self.value = value

        fake_role = MockRole("nonexistent_role")
        result = has_permission(fake_role, Permission.VIEW_MEMBERS)

        # Should return False for undefined roles
        assert result is False

    def test_has_permission_function_signature(self):
        """Test that has_permission function has correct signature and return type."""
        # Test with valid inputs
        result = has_permission(OrganizationRole.admin, Permission.VIEW_MEMBERS)
        assert isinstance(result, bool)

        # Test return type consistency
        true_result = has_permission(OrganizationRole.owner, Permission.VIEW_MEMBERS)
        false_result = has_permission(OrganizationRole.user, Permission.VIEW_MEMBERS)

        assert true_result is True
        assert false_result is False


class TestPermissionSystemIntegrity:
    """Test overall permission system integrity and consistency."""

    def test_permission_hierarchy_consistency(self):
        """Test that permission hierarchy makes logical sense."""
        # Owner should have all permissions that admin has, plus more
        owner_perms = ROLE_PERMISSIONS[OrganizationRole.owner]
        admin_perms = ROLE_PERMISSIONS[OrganizationRole.admin]

        assert admin_perms.issubset(owner_perms)
        assert len(owner_perms) > len(admin_perms)

    def test_view_members_permission_distribution(self):
        """Test that VIEW_MEMBERS permission is distributed to appropriate roles."""
        roles_with_view = [
            role
            for role, perms in ROLE_PERMISSIONS.items()
            if Permission.VIEW_MEMBERS in perms
        ]

        expected_roles_with_view = [
            OrganizationRole.owner,
            OrganizationRole.admin,
            OrganizationRole.auditor,
        ]

        assert set(roles_with_view) == set(expected_roles_with_view)

    def test_destructive_permissions_restricted(self):
        """Test that destructive permissions are restricted to higher roles."""
        destructive_permissions = {
            Permission.MANAGE_MEMBERS,  # Includes ability to remove members
            Permission.MANAGE_BILLING,
        }

        # Only owner and admin should have destructive permissions
        # (admin doesn't have billing, but has remove members)
        for permission in destructive_permissions:
            roles_with_permission = [
                role for role, perms in ROLE_PERMISSIONS.items() if permission in perms
            ]

            # Ensure only high-privilege roles have these permissions
            for role in roles_with_permission:
                assert role in [OrganizationRole.owner, OrganizationRole.admin]

    def test_permission_mapping_immutability(self):
        """Test that permission mappings are properly defined as sets."""
        for role, permissions in ROLE_PERMISSIONS.items():
            assert isinstance(permissions, set)

            # Each permission should be a Permission enum member
            for permission in permissions:
                assert isinstance(permission, Permission)
