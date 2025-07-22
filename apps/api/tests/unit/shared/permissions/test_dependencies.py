"""
Tests for shared permissions dependencies (require_permission function).
"""

from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException
from prisma.enums import OrganizationRole
from prisma.models import OrganizationMember, Profile

from src.shared.permissions.dependencies import require_permission
from src.shared.permissions.models import Permission


class TestRequirePermission:
    """Test the require_permission dependency factory."""

    @pytest.fixture
    def mock_profile(self) -> Mock:
        """Mock Profile for authenticated user."""
        profile = Mock(spec=Profile)
        profile.id = "test-profile-id-123"
        profile.email = "test@example.com"
        profile.displayName = "Test User"
        return profile

    @pytest.fixture
    def mock_owner_membership(self) -> Mock:
        """Mock OrganizationMember with owner role."""
        membership = Mock(spec=OrganizationMember)
        membership.id = "membership-123"
        membership.role = OrganizationRole.owner
        membership.status = "active"
        membership.organizationId = "test-org-id-123"
        return membership

    @pytest.fixture
    def mock_admin_membership(self) -> Mock:
        """Mock OrganizationMember with admin role."""
        membership = Mock(spec=OrganizationMember)
        membership.id = "membership-456"
        membership.role = OrganizationRole.admin
        membership.status = "active"
        membership.organizationId = "test-org-id-123"
        return membership

    @pytest.fixture
    def mock_user_membership(self) -> Mock:
        """Mock OrganizationMember with user role."""
        membership = Mock(spec=OrganizationMember)
        membership.id = "membership-789"
        membership.role = OrganizationRole.user
        membership.status = "active"
        membership.organizationId = "test-org-id-123"
        return membership

    @pytest.mark.asyncio
    async def test_require_permission_owner_success(
        self, mock_profile: Mock, mock_owner_membership: Mock
    ):
        """Test that owner with all permissions can access any endpoint."""
        org_id = str(uuid4())

        # Test with MANAGE_BILLING permission (only owners have this)
        permission_dependency = require_permission(Permission.MANAGE_BILLING)

        with (
            patch("src.shared.permissions.dependencies.get_db") as mock_get_db,
            patch(
                "src.shared.permissions.dependencies.get_current_profile"
            ) as mock_get_profile,
            patch(
                "src.shared.permissions.dependencies.validate_organization_access"
            ) as mock_validate_access,
        ):
            mock_db = Mock()
            mock_get_db.return_value = mock_db
            mock_get_profile.return_value = mock_profile
            mock_validate_access.return_value = mock_owner_membership

            # Act
            result = await permission_dependency(
                org_id=org_id,
                profile=mock_profile,
                db=mock_db,
            )

            # Assert
            assert result == mock_owner_membership
            mock_validate_access.assert_called_once_with(
                mock_profile.id, org_id, mock_db
            )

    @pytest.mark.asyncio
    async def test_require_permission_admin_success(
        self, mock_profile: Mock, mock_admin_membership: Mock
    ):
        """Test that admin with appropriate permissions can access endpoints."""
        org_id = str(uuid4())

        # Test with MANAGE_BANK_ACCOUNTS permission (admins have this)
        permission_dependency = require_permission(Permission.MANAGE_BANK_ACCOUNTS)

        with (
            patch(
                "src.shared.permissions.dependencies.validate_organization_access"
            ) as mock_validate_access,
        ):
            mock_db = Mock()
            mock_validate_access.return_value = mock_admin_membership

            # Act
            result = await permission_dependency(
                org_id=org_id,
                profile=mock_profile,
                db=mock_db,
            )

            # Assert
            assert result == mock_admin_membership

    @pytest.mark.asyncio
    async def test_require_permission_admin_forbidden_billing(
        self, mock_profile: Mock, mock_admin_membership: Mock
    ):
        """Test that admin without billing permission is forbidden."""
        org_id = str(uuid4())

        # Test with MANAGE_BILLING permission (admins don't have this)
        permission_dependency = require_permission(Permission.MANAGE_BILLING)

        with (
            patch(
                "src.shared.permissions.dependencies.validate_organization_access"
            ) as mock_validate_access,
        ):
            mock_db = Mock()
            mock_validate_access.return_value = mock_admin_membership

            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                await permission_dependency(
                    org_id=org_id,
                    profile=mock_profile,
                    db=mock_db,
                )

            assert exc_info.value.status_code == 403
            assert "manage_billing required" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_require_permission_user_forbidden_management(
        self, mock_profile: Mock, mock_user_membership: Mock
    ):
        """Test that basic user is forbidden from management operations."""
        org_id = str(uuid4())

        # Test with MANAGE_MEMBERS permission (users don't have this)
        permission_dependency = require_permission(Permission.MANAGE_MEMBERS)

        with (
            patch(
                "src.shared.permissions.dependencies.validate_organization_access"
            ) as mock_validate_access,
        ):
            mock_db = Mock()
            mock_validate_access.return_value = mock_user_membership

            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                await permission_dependency(
                    org_id=org_id,
                    profile=mock_profile,
                    db=mock_db,
                )

            assert exc_info.value.status_code == 403
            assert "manage_members required" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_require_permission_user_success_view_bank_accounts(
        self, mock_profile: Mock, mock_user_membership: Mock
    ):
        """Test that basic user can view bank accounts."""
        org_id = str(uuid4())

        # Test with VIEW_BANK_ACCOUNTS permission (users have this)
        permission_dependency = require_permission(Permission.VIEW_BANK_ACCOUNTS)

        with (
            patch(
                "src.shared.permissions.dependencies.validate_organization_access"
            ) as mock_validate_access,
        ):
            mock_db = Mock()
            mock_validate_access.return_value = mock_user_membership

            # Act
            result = await permission_dependency(
                org_id=org_id,
                profile=mock_profile,
                db=mock_db,
            )

            # Assert
            assert result == mock_user_membership

    @pytest.mark.asyncio
    async def test_require_permission_organization_access_denied(
        self, mock_profile: Mock
    ):
        """Test that permission check fails if user has no org access."""
        org_id = str(uuid4())

        permission_dependency = require_permission(Permission.VIEW_MEMBERS)

        with (
            patch(
                "src.shared.permissions.dependencies.validate_organization_access"
            ) as mock_validate_access,
        ):
            mock_db = Mock()
            # Mock validate_organization_access raising HTTPException
            mock_validate_access.side_effect = HTTPException(
                status_code=403, detail="Access denied to organization"
            )

            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                await permission_dependency(
                    org_id=org_id,
                    profile=mock_profile,
                    db=mock_db,
                )

            assert exc_info.value.status_code == 403
            assert "Access denied to organization" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_require_permission_factory_creates_unique_functions(self):
        """Test that require_permission factory creates unique functions."""
        permission_dep_1 = require_permission(Permission.VIEW_MEMBERS)
        permission_dep_2 = require_permission(Permission.MANAGE_MEMBERS)

        # Functions should be different objects
        assert permission_dep_1 != permission_dep_2
        assert permission_dep_1.__name__ == "check_permission"
        assert permission_dep_2.__name__ == "check_permission"

    @pytest.mark.parametrize(
        "permission,role,should_succeed",
        [
            (Permission.VIEW_MEMBERS, OrganizationRole.owner, True),
            (Permission.VIEW_MEMBERS, OrganizationRole.admin, True),
            (Permission.VIEW_MEMBERS, OrganizationRole.auditor, True),
            (Permission.VIEW_MEMBERS, OrganizationRole.user, False),
            (Permission.MANAGE_MEMBERS, OrganizationRole.owner, True),
            (Permission.MANAGE_MEMBERS, OrganizationRole.admin, True),
            (Permission.MANAGE_MEMBERS, OrganizationRole.auditor, False),
            (Permission.MANAGE_MEMBERS, OrganizationRole.user, False),
            (Permission.MANAGE_BILLING, OrganizationRole.owner, True),
            (Permission.MANAGE_BILLING, OrganizationRole.admin, False),
            (Permission.MANAGE_BILLING, OrganizationRole.auditor, False),
            (Permission.MANAGE_BILLING, OrganizationRole.user, False),
            (Permission.VIEW_BANK_ACCOUNTS, OrganizationRole.owner, True),
            (Permission.VIEW_BANK_ACCOUNTS, OrganizationRole.admin, True),
            (Permission.VIEW_BANK_ACCOUNTS, OrganizationRole.auditor, True),
            (Permission.VIEW_BANK_ACCOUNTS, OrganizationRole.user, True),
            (Permission.MANAGE_BANK_ACCOUNTS, OrganizationRole.owner, True),
            (Permission.MANAGE_BANK_ACCOUNTS, OrganizationRole.admin, True),
            (Permission.MANAGE_BANK_ACCOUNTS, OrganizationRole.auditor, False),
            (Permission.MANAGE_BANK_ACCOUNTS, OrganizationRole.user, False),
        ],
    )
    @pytest.mark.asyncio
    async def test_permission_role_combinations(
        self,
        permission: Permission,
        role: OrganizationRole,
        should_succeed: bool,
        mock_profile: Mock,
    ):
        """Test all permission-role combinations systematically."""
        org_id = str(uuid4())

        # Create mock membership with the specified role
        mock_membership = Mock(spec=OrganizationMember)
        mock_membership.role = role
        mock_membership.id = f"membership-{role.value}"
        mock_membership.organizationId = org_id

        permission_dependency = require_permission(permission)

        with (
            patch(
                "src.shared.permissions.dependencies.validate_organization_access"
            ) as mock_validate_access,
        ):
            mock_db = Mock()
            mock_validate_access.return_value = mock_membership

            if should_succeed:
                # Should succeed
                result = await permission_dependency(
                    org_id=org_id,
                    profile=mock_profile,
                    db=mock_db,
                )
                assert result == mock_membership
            else:
                # Should raise HTTPException
                with pytest.raises(HTTPException) as exc_info:
                    await permission_dependency(
                        org_id=org_id,
                        profile=mock_profile,
                        db=mock_db,
                    )

                assert exc_info.value.status_code == 403
                assert permission.value in exc_info.value.detail
