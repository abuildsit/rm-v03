"""
Tests for organization dependencies in src/domains/organizations/dependencies.py

Tests the authorization dependency factory and permission validation.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import HTTPException
from prisma.enums import OrganizationRole
from prisma.models import OrganizationMember, Profile

from src.shared.permissions import Permission, require_permission


class TestRequirePermissionFactory:
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
    def mock_admin_membership(self) -> Mock:
        """Mock OrganizationMember with admin role."""
        membership = Mock(spec=OrganizationMember)
        membership.id = "membership-123"
        membership.profileId = "test-profile-id-123"
        membership.organizationId = "test-org-456"
        membership.role = OrganizationRole.admin
        membership.status = "active"
        return membership

    @pytest.fixture
    def mock_user_membership(self) -> Mock:
        """Mock OrganizationMember with user role (no special permissions)."""
        membership = Mock(spec=OrganizationMember)
        membership.id = "membership-789"
        membership.profileId = "test-profile-id-123"
        membership.organizationId = "test-org-456"
        membership.role = OrganizationRole.user
        membership.status = "active"
        return membership

    def test_require_permission_returns_callable(self):
        """Test that require_permission returns a callable function."""
        dependency_func = require_permission(Permission.VIEW_MEMBERS)

        assert callable(dependency_func)
        assert hasattr(dependency_func, "__call__")

    def test_require_permission_factory_creates_different_functions(self):
        """Test that factory creates different functions for different permissions."""
        view_dependency = require_permission(Permission.VIEW_MEMBERS)
        manage_dependency = require_permission(Permission.MANAGE_MEMBERS)

        assert view_dependency != manage_dependency
        assert callable(view_dependency)
        assert callable(manage_dependency)

    @pytest.mark.asyncio
    async def test_dependency_validates_permission_success_admin(
        self, mock_profile: Mock, mock_admin_membership: Mock
    ):
        """Test successful permission validation for admin user."""
        org_id = "test-org-456"

        # Mock the validate_organization_access function
        with patch(
            "src.shared.permissions.dependencies.validate_organization_access",
            new_callable=AsyncMock,
        ) as mock_validate:
            mock_validate.return_value = mock_admin_membership

            # Create dependency for VIEW_MEMBERS permission
            check_permission = require_permission(Permission.VIEW_MEMBERS)

            # Mock database
            mock_db = Mock()

            # Act
            result = await check_permission(org_id, mock_profile, mock_db)

            # Assert
            assert result == mock_admin_membership
            mock_validate.assert_called_once_with(mock_profile.id, org_id, mock_db)

    @pytest.mark.asyncio
    async def test_dependency_validates_permission_success_owner(
        self, mock_profile: Mock
    ):
        """Test successful permission validation for owner user."""
        org_id = "test-org-456"

        # Mock owner membership
        owner_membership = Mock(spec=OrganizationMember)
        owner_membership.role = OrganizationRole.owner
        owner_membership.status = "active"

        # Mock the validate_organization_access function
        with patch(
            "src.shared.permissions.dependencies.validate_organization_access",
            new_callable=AsyncMock,
        ) as mock_validate:
            mock_validate.return_value = owner_membership

            # Create dependency for MANAGE_BILLING permission (owner only)
            check_permission = require_permission(Permission.MANAGE_BILLING)

            # Mock database
            mock_db = Mock()

            # Act
            result = await check_permission(org_id, mock_profile, mock_db)

            # Assert
            assert result == owner_membership

    @pytest.mark.asyncio
    async def test_dependency_validates_permission_success_auditor(
        self, mock_profile: Mock
    ):
        """Test successful permission validation for auditor user."""
        org_id = "test-org-456"

        # Mock auditor membership
        auditor_membership = Mock(spec=OrganizationMember)
        auditor_membership.role = OrganizationRole.auditor
        auditor_membership.status = "active"

        # Mock the validate_organization_access function
        with patch(
            "src.shared.permissions.dependencies.validate_organization_access",
            new_callable=AsyncMock,
        ) as mock_validate:
            mock_validate.return_value = auditor_membership

            # Create dependency for VIEW_MEMBERS permission
            check_permission = require_permission(Permission.VIEW_MEMBERS)

            # Mock database
            mock_db = Mock()

            # Act
            result = await check_permission(org_id, mock_profile, mock_db)

            # Assert
            assert result == auditor_membership

    @pytest.mark.asyncio
    async def test_dependency_denies_permission_insufficient_role(
        self, mock_profile: Mock, mock_user_membership: Mock
    ):
        """Test permission denied for user with insufficient role."""
        org_id = "test-org-456"

        # Mock the validate_organization_access function
        with patch(
            "src.shared.permissions.dependencies.validate_organization_access",
            new_callable=AsyncMock,
        ) as mock_validate:
            mock_validate.return_value = mock_user_membership

            # Create dependency for VIEW_MEMBERS permission (user role lacks this)
            check_permission = require_permission(Permission.VIEW_MEMBERS)

            # Mock database
            mock_db = Mock()

            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                await check_permission(org_id, mock_profile, mock_db)

            assert exc_info.value.status_code == 403
            assert "Insufficient permissions" in exc_info.value.detail
            assert "view_members required" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_dependency_denies_admin_billing_permission(
        self, mock_profile: Mock, mock_admin_membership: Mock
    ):
        """Test permission denied for admin trying to access billing (owner-only)."""
        org_id = "test-org-456"

        # Mock the validate_organization_access function
        with patch(
            "src.shared.permissions.dependencies.validate_organization_access",
            new_callable=AsyncMock,
        ) as mock_validate:
            mock_validate.return_value = mock_admin_membership

            # Create dependency for MANAGE_BILLING permission (owner only)
            check_permission = require_permission(Permission.MANAGE_BILLING)

            # Mock database
            mock_db = Mock()

            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                await check_permission(org_id, mock_profile, mock_db)

            assert exc_info.value.status_code == 403
            assert "Insufficient permissions" in exc_info.value.detail
            assert "manage_billing required" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_dependency_organization_access_validation_fails(
        self, mock_profile: Mock
    ):
        """Test handling when user is not a member of organization."""
        org_id = "test-org-456"

        # Mock the validate_organization_access function to raise HTTPException
        with patch(
            "src.shared.permissions.dependencies.validate_organization_access",
            new_callable=AsyncMock,
        ) as mock_validate:
            mock_validate.side_effect = HTTPException(
                status_code=403, detail="Access denied to organization"
            )

            # Create dependency for any permission
            check_permission = require_permission(Permission.VIEW_MEMBERS)

            # Mock database
            mock_db = Mock()

            # Act & Assert - organization access validation should fail first
            with pytest.raises(HTTPException) as exc_info:
                await check_permission(org_id, mock_profile, mock_db)

            assert exc_info.value.status_code == 403
            assert "Access denied to organization" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_dependency_passes_correct_parameters(
        self, mock_profile: Mock, mock_admin_membership: Mock
    ):
        """Test that dependency passes correct parameters to validation."""
        org_id = "test-org-456"

        # Mock the validate_organization_access function
        with patch(
            "src.shared.permissions.dependencies.validate_organization_access",
            new_callable=AsyncMock,
        ) as mock_validate:
            mock_validate.return_value = mock_admin_membership

            # Create dependency
            check_permission = require_permission(Permission.EDIT_ORGANIZATION)

            # Mock database
            mock_db = Mock()

            # Act
            await check_permission(org_id, mock_profile, mock_db)

            # Assert correct parameters were passed
            mock_validate.assert_called_once_with(
                mock_profile.id,  # profile_id extracted from profile
                org_id,  # org_id from parameter
                mock_db,  # database connection
            )

    @pytest.mark.asyncio
    async def test_dependency_different_permissions_work_independently(
        self, mock_profile: Mock, mock_admin_membership: Mock
    ):
        """Test that different permission dependencies work independently."""
        org_id = "test-org-456"
        mock_db = Mock()

        # Mock the validate_organization_access function
        with patch(
            "src.shared.permissions.dependencies.validate_organization_access",
            new_callable=AsyncMock,
        ) as mock_validate:
            mock_validate.return_value = mock_admin_membership

            # Test multiple permissions that admin should have
            view_permission = require_permission(Permission.VIEW_MEMBERS)
            manage_permission = require_permission(Permission.MANAGE_MEMBERS)
            edit_permission = require_permission(Permission.EDIT_ORGANIZATION)

            # All should succeed for admin
            result1 = await view_permission(org_id, mock_profile, mock_db)
            result2 = await manage_permission(org_id, mock_profile, mock_db)
            result3 = await edit_permission(org_id, mock_profile, mock_db)

            assert result1 == mock_admin_membership
            assert result2 == mock_admin_membership
            assert result3 == mock_admin_membership

            # But billing should fail for admin
            billing_permission = require_permission(Permission.MANAGE_BILLING)
            with pytest.raises(HTTPException) as exc_info:
                await billing_permission(org_id, mock_profile, mock_db)

            assert exc_info.value.status_code == 403

    def test_dependency_function_docstring_and_metadata(self):
        """Test that generated dependency functions have proper metadata."""
        check_permission = require_permission(Permission.VIEW_MEMBERS)

        # Should be an async function
        import asyncio

        assert asyncio.iscoroutinefunction(check_permission)

        # Should have proper function name (though it might be dynamically generated)
        assert hasattr(check_permission, "__name__")

        # Should return the expected type hint (though we can't easily test this)
        assert callable(check_permission)
