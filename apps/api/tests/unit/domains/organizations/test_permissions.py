"""
Tests for organization-specific permission logic.

Note: Core permission system tests are in tests/unit/shared/permissions/
This file only tests organization-domain-specific permission behavior.
"""

from prisma.enums import OrganizationRole

from src.shared.permissions import (
    ROLE_PERMISSIONS,
    Permission,
    has_permission,
)


class TestOrganizationSpecificPermissions:
    """Test organization-specific permission scenarios."""

    def test_organization_management_permissions(self):
        """Test that organization management permissions are properly distributed."""
        # Only owners and admins should be able to manage members
        manage_member_roles = [
            role
            for role, perms in ROLE_PERMISSIONS.items()
            if Permission.MANAGE_MEMBERS in perms
        ]
        assert OrganizationRole.owner in manage_member_roles
        assert OrganizationRole.admin in manage_member_roles
        assert OrganizationRole.auditor not in manage_member_roles
        assert OrganizationRole.user not in manage_member_roles

        # Only owners should be able to manage billing
        billing_roles = [
            role
            for role, perms in ROLE_PERMISSIONS.items()
            if Permission.MANAGE_BILLING in perms
        ]
        assert billing_roles == [OrganizationRole.owner]

    def test_has_permission_function(self):
        """Test the has_permission utility function."""
        # Test with owner role
        assert has_permission(OrganizationRole.owner, Permission.MANAGE_BILLING)
        assert has_permission(OrganizationRole.owner, Permission.VIEW_MEMBERS)

        # Test with admin role
        assert has_permission(OrganizationRole.admin, Permission.MANAGE_MEMBERS)
        assert not has_permission(OrganizationRole.admin, Permission.MANAGE_BILLING)

        # Test with auditor role
        assert has_permission(OrganizationRole.auditor, Permission.VIEW_MEMBERS)
        assert not has_permission(OrganizationRole.auditor, Permission.MANAGE_MEMBERS)

        # Test with user role
        assert has_permission(OrganizationRole.user, Permission.VIEW_BANK_ACCOUNTS)
        assert not has_permission(OrganizationRole.user, Permission.MANAGE_MEMBERS)

    def test_organization_visibility_permissions(self):
        """Test that visibility permissions are correctly distributed."""
        # All roles should be able to view bank accounts for transparency
        for role in OrganizationRole:
            assert has_permission(role, Permission.VIEW_BANK_ACCOUNTS)

        # Only certain roles should see member lists
        view_member_roles = [
            role
            for role, perms in ROLE_PERMISSIONS.items()
            if Permission.VIEW_MEMBERS in perms
        ]
        assert OrganizationRole.owner in view_member_roles
        assert OrganizationRole.admin in view_member_roles
        assert OrganizationRole.auditor in view_member_roles
        assert OrganizationRole.user not in view_member_roles
