"""
Dynamic permission testing utilities for sustainable test maintenance.

These utilities automatically derive expected permissions and role mappings from
the actual Permission enum and ROLE_PERMISSIONS, making tests resilient to
new permissions being added.
"""

from typing import Dict, Set

from prisma.enums import OrganizationRole

from src.shared.permissions.models import ROLE_PERMISSIONS, Permission


class PermissionTestHelpers:
    """Helper class for dynamic permission testing."""

    @staticmethod
    def get_all_permissions() -> Set[Permission]:
        """Get all available permissions from the Permission enum."""
        return set(Permission)

    @staticmethod
    def get_role_permissions(role: OrganizationRole) -> Set[Permission]:
        """Get permissions for a specific role."""
        return ROLE_PERMISSIONS.get(role, set())

    @staticmethod
    def get_permissions_by_category() -> Dict[str, Set[Permission]]:
        """
        Categorize permissions by their domain/resource type.

        Returns a mapping of category -> permissions for that category.
        Categories are automatically derived from permission names.
        """
        categories: Dict[str, Set[Permission]] = {}

        for permission in Permission:
            # Extract category from permission name (after first underscore)
            parts = permission.name.split("_", 1)
            if len(parts) > 1:
                category = parts[1].lower()  # e.g., "members", "bank_accounts", etc.
                if category not in categories:
                    categories[category] = set()
                categories[category].add(permission)
            else:
                # Handle permissions without category
                if "misc" not in categories:
                    categories["misc"] = set()
                categories["misc"].add(permission)

        return categories

    @staticmethod
    def get_view_permissions() -> Set[Permission]:
        """Get all VIEW_* permissions."""
        return {p for p in Permission if p.name.startswith("VIEW_")}

    @staticmethod
    def get_manage_permissions() -> Set[Permission]:
        """Get all MANAGE_* permissions."""
        return {p for p in Permission if p.name.startswith("MANAGE_")}

    @staticmethod
    def get_create_permissions() -> Set[Permission]:
        """Get all CREATE_* permissions."""
        return {p for p in Permission if p.name.startswith("CREATE_")}

    @staticmethod
    def get_approve_permissions() -> Set[Permission]:
        """Get all APPROVE_* permissions."""
        return {p for p in Permission if p.name.startswith("APPROVE_")}

    @staticmethod
    def get_destructive_permissions() -> Set[Permission]:
        """
        Get permissions that are considered destructive/high-risk.

        These should typically be restricted to higher privilege roles.
        """
        destructive = set()

        # Any MANAGE permission is potentially destructive
        destructive.update(PermissionTestHelpers.get_manage_permissions())

        # Billing is especially sensitive
        destructive.update(p for p in Permission if "BILLING" in p.name)

        # Any DELETE permissions (if they exist)
        destructive.update(p for p in Permission if p.name.startswith("DELETE_"))

        return destructive

    @staticmethod
    def validate_role_hierarchy() -> bool:
        """
        Validate that the role hierarchy makes logical sense.

        Owner should have all permissions.
        Admin should be a subset of owner (except possibly billing).
        Lower roles should have progressively fewer permissions.
        """
        owner_perms = PermissionTestHelpers.get_role_permissions(OrganizationRole.owner)
        admin_perms = PermissionTestHelpers.get_role_permissions(OrganizationRole.admin)

        # Owner should have all permissions
        all_perms = PermissionTestHelpers.get_all_permissions()
        if owner_perms != all_perms:
            return False

        # Admin permissions should be a subset of owner (allowing for billing exception)
        if not (admin_perms <= owner_perms):
            return False

        # Owner should have more permissions than admin
        if len(owner_perms) <= len(admin_perms):
            return False

        return True

    @staticmethod
    def get_permissions_missing_from_role(
        role: OrganizationRole, expected_permissions: Set[Permission]
    ) -> Set[Permission]:
        """Get permissions that a role should have but doesn't."""
        actual_permissions = PermissionTestHelpers.get_role_permissions(role)
        return expected_permissions - actual_permissions

    @staticmethod
    def get_unexpected_permissions_for_role(
        role: OrganizationRole, expected_permissions: Set[Permission]
    ) -> Set[Permission]:
        """Get permissions that a role has but shouldn't."""
        actual_permissions = PermissionTestHelpers.get_role_permissions(role)
        return actual_permissions - expected_permissions

    @staticmethod
    def assert_role_has_exactly_permissions(
        role: OrganizationRole, expected_permissions: Set[Permission]
    ) -> None:
        """
        Assert that a role has exactly the expected permissions.

        Provides detailed error messages about missing or unexpected permissions.
        """

        missing = PermissionTestHelpers.get_permissions_missing_from_role(
            role, expected_permissions
        )
        unexpected = PermissionTestHelpers.get_unexpected_permissions_for_role(
            role, expected_permissions
        )

        error_parts = []
        if missing:
            missing_names = [p.name for p in missing]
            error_parts.append(f"Missing permissions: {missing_names}")

        if unexpected:
            unexpected_names = [p.name for p in unexpected]
            error_parts.append(f"Unexpected permissions: {unexpected_names}")

        if error_parts:
            error_msg = f"Role {role.value} permission mismatch. " + "; ".join(
                error_parts
            )
            raise AssertionError(error_msg)

    @staticmethod
    def assert_role_has_permission_types(
        role: OrganizationRole,
        should_have_view: bool = True,
        should_have_manage: bool = False,
        should_have_create: bool = False,
        should_have_approve: bool = False,
    ) -> None:
        """
        Assert that a role has the expected types of permissions.

        This is useful for testing role characteristics without hardcoding
        specific permission lists.
        """
        role_permissions = PermissionTestHelpers.get_role_permissions(role)

        view_perms = role_permissions & PermissionTestHelpers.get_view_permissions()
        manage_perms = role_permissions & PermissionTestHelpers.get_manage_permissions()
        create_perms = role_permissions & PermissionTestHelpers.get_create_permissions()
        approve_perms = (
            role_permissions & PermissionTestHelpers.get_approve_permissions()
        )

        if should_have_view and not view_perms:
            raise AssertionError(
                f"Role {role.value} should have VIEW permissions but has none"
            )
        elif not should_have_view and view_perms:
            perm_names = [p.name for p in view_perms]
            raise AssertionError(
                f"Role {role.value} should not have VIEW permissions "
                f"but has: {perm_names}"
            )

        if should_have_manage and not manage_perms:
            raise AssertionError(
                f"Role {role.value} should have MANAGE permissions but has none"
            )
        elif not should_have_manage and manage_perms:
            perm_names = [p.name for p in manage_perms]
            raise AssertionError(
                f"Role {role.value} should not have MANAGE permissions "
                f"but has: {perm_names}"
            )

        if should_have_create and not create_perms:
            raise AssertionError(
                f"Role {role.value} should have CREATE permissions but has none"
            )
        elif not should_have_create and create_perms:
            perm_names = [p.name for p in create_perms]
            raise AssertionError(
                f"Role {role.value} should not have CREATE permissions "
                f"but has: {perm_names}"
            )

        if should_have_approve and not approve_perms:
            raise AssertionError(
                f"Role {role.value} should have APPROVE permissions but has none"
            )
        elif not should_have_approve and approve_perms:
            perm_names = [p.name for p in approve_perms]
            raise AssertionError(
                f"Role {role.value} should not have APPROVE permissions "
                f"but has: {perm_names}"
            )
