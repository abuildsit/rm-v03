"""
Tests for organization service functions in src/domains/organizations/service.py

Tests the core organization creation functionality and business logic.
"""

from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest
from prisma.enums import MemberStatus, OrganizationRole
from prisma.errors import PrismaError
from prisma.models import Profile

from src.domains.organizations.models import (
    CreateOrganizationResponse,
    OrganizationCreate,
    OrganizationResponse,
)
from src.domains.organizations.service import OrganizationService


class TestOrganizationService:
    """Test OrganizationService for organization management."""

    @pytest.fixture
    def mock_profile(self) -> Mock:
        """Mock Profile object for testing."""
        profile = Mock(spec=Profile)
        profile.id = "test-profile-id-123"
        profile.email = "test@example.com"
        profile.displayName = "Test User"
        return profile

    @pytest.fixture
    def organization_create_request(self) -> OrganizationCreate:
        """Valid organization creation request."""
        return OrganizationCreate(name="Test Organization")

    @pytest.fixture
    def organization_create_request_special_chars(self) -> OrganizationCreate:
        """Organization creation request with special characters."""
        return OrganizationCreate(name="Acme Corp & Associates - Ltd.")

    @pytest.mark.asyncio
    async def test_create_organization_success(
        self,
        mock_prisma: Mock,
        mock_profile: Mock,
        organization_create_request: OrganizationCreate,
        mock_organization: Mock,
        mock_organization_member_owner: Mock,
    ):
        """Test successful organization creation with owner membership."""
        # Arrange
        mock_prisma.organization.create.return_value = mock_organization
        mock_prisma.organizationmember.create.return_value = (
            mock_organization_member_owner
        )

        # Act
        service = OrganizationService(mock_prisma)
        result = await service.create_organization(
            organization_create_request, mock_profile
        )

        # Assert
        assert isinstance(result, CreateOrganizationResponse)
        assert isinstance(result.organization, OrganizationResponse)

        # Verify organization data
        assert result.organization.id == "test-org-id-123"
        assert result.organization.name == "Test Organization"
        assert result.organization.subscription_tier == "basic"
        assert result.organization.created_at == "2024-01-15T09:00:00"
        assert result.organization.updated_at == "2024-01-15T09:00:00"

        # Verify role data
        assert result.role == "owner"

        # Verify database calls
        mock_prisma.organization.create.assert_called_once()
        mock_prisma.organizationmember.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_organization_database_calls_correct_parameters(
        self,
        mock_prisma: Mock,
        mock_profile: Mock,
        organization_create_request: OrganizationCreate,
        mock_organization: Mock,
        mock_organization_member_owner: Mock,
    ):
        """Test that database calls use correct parameters."""
        # Arrange
        mock_prisma.organization.create.return_value = mock_organization
        mock_prisma.organizationmember.create.return_value = (
            mock_organization_member_owner
        )

        # Act
        service = OrganizationService(mock_prisma)
        await service.create_organization(organization_create_request, mock_profile)

        # Assert organization creation parameters
        org_call_args = mock_prisma.organization.create.call_args
        org_data = org_call_args[1]["data"]
        assert org_data["name"] == "Test Organization"
        assert org_data["subscriptionTier"] == "basic"

        # Assert membership creation parameters
        member_call_args = mock_prisma.organizationmember.create.call_args
        member_data = member_call_args[1]["data"]
        assert member_data["profileId"] == "test-profile-id-123"
        assert member_data["organizationId"] == "test-org-id-123"
        assert member_data["role"] == OrganizationRole.owner
        assert member_data["status"] == MemberStatus.active

    @pytest.mark.asyncio
    async def test_create_organization_with_special_characters(
        self,
        mock_prisma: Mock,
        mock_profile: Mock,
        organization_create_request_special_chars: OrganizationCreate,
        mock_organization: Mock,
        mock_organization_member_owner: Mock,
    ):
        """Test organization creation with special characters in name."""
        # Arrange
        mock_organization.name = "Acme Corp & Associates - Ltd."
        mock_prisma.organization.create.return_value = mock_organization
        mock_prisma.organizationmember.create.return_value = (
            mock_organization_member_owner
        )

        # Act
        service = OrganizationService(mock_prisma)
        result = await service.create_organization(
            organization_create_request_special_chars, mock_profile
        )

        # Assert
        assert result.organization.name == "Acme Corp & Associates - Ltd."

        # Verify database call
        org_call_args = mock_prisma.organization.create.call_args
        org_data = org_call_args[1]["data"]
        assert org_data["name"] == "Acme Corp & Associates - Ltd."

    @pytest.mark.asyncio
    async def test_create_organization_handles_none_timestamps(
        self,
        mock_prisma: Mock,
        mock_profile: Mock,
        organization_create_request: OrganizationCreate,
        mock_organization_member_owner: Mock,
    ):
        """Test organization creation handles None timestamps gracefully."""
        # Arrange
        mock_organization = Mock()
        mock_organization.id = "test-org-id-123"
        mock_organization.name = "Test Organization"
        mock_organization.subscriptionTier = "basic"
        mock_organization.createdAt = None
        mock_organization.updatedAt = None

        mock_prisma.organization.create.return_value = mock_organization
        mock_prisma.organizationmember.create.return_value = (
            mock_organization_member_owner
        )

        # Act
        service = OrganizationService(mock_prisma)
        result = await service.create_organization(
            organization_create_request, mock_profile
        )

        # Assert
        assert result.organization.created_at is None
        assert result.organization.updated_at is None

    @pytest.mark.asyncio
    async def test_create_organization_enum_conversion(
        self,
        mock_prisma: Mock,
        mock_profile: Mock,
        organization_create_request: OrganizationCreate,
        mock_organization: Mock,
    ):
        """Test that enum values are properly converted to strings in response."""
        # Arrange
        mock_member = Mock()
        mock_member.id = "test-member-id"
        mock_member.role = OrganizationRole.owner

        mock_prisma.organization.create.return_value = mock_organization
        mock_prisma.organizationmember.create.return_value = mock_member

        # Act
        service = OrganizationService(mock_prisma)
        result = await service.create_organization(
            organization_create_request, mock_profile
        )

        # Assert that role enum is converted to string
        assert result.role == "owner"
        assert isinstance(result.role, str)

    @pytest.mark.asyncio
    async def test_create_organization_database_error_during_org_creation(
        self,
        mock_prisma: Mock,
        mock_profile: Mock,
        organization_create_request: OrganizationCreate,
    ):
        """Test error handling when organization creation fails."""
        # Arrange
        mock_prisma.organization.create.side_effect = PrismaError(
            "Database connection failed"
        )

        # Act & Assert
        service = OrganizationService(mock_prisma)
        with pytest.raises(PrismaError) as exc_info:
            await service.create_organization(organization_create_request, mock_profile)

        assert "Database connection failed" in str(exc_info.value)

        # Verify that membership creation was never called
        mock_prisma.organizationmember.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_organization_database_error_during_membership_creation(
        self,
        mock_prisma: Mock,
        mock_profile: Mock,
        organization_create_request: OrganizationCreate,
        mock_organization: Mock,
    ):
        """Test error handling when membership creation fails after org creation."""
        # Arrange
        mock_prisma.organization.create.return_value = mock_organization
        mock_prisma.organizationmember.create.side_effect = PrismaError(
            "Membership creation failed"
        )

        # Act & Assert
        service = OrganizationService(mock_prisma)
        with pytest.raises(PrismaError) as exc_info:
            await service.create_organization(organization_create_request, mock_profile)

        assert "Membership creation failed" in str(exc_info.value)

        # Verify that organization was created
        mock_prisma.organization.create.assert_called_once()
        # Verify that membership creation was attempted
        mock_prisma.organizationmember.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_organization_constraint_violation_unique_name(
        self,
        mock_prisma: Mock,
        mock_profile: Mock,
        organization_create_request: OrganizationCreate,
    ):
        """Test handling of constraint violations (e.g., duplicate org name)."""
        # Arrange
        mock_prisma.organization.create.side_effect = PrismaError(
            "Unique constraint failed on the fields: (`name`)"
        )

        # Act & Assert
        service = OrganizationService(mock_prisma)
        with pytest.raises(PrismaError) as exc_info:
            await service.create_organization(organization_create_request, mock_profile)

        assert "Unique constraint failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_create_organization_different_profiles(
        self,
        mock_prisma: Mock,
        organization_create_request: OrganizationCreate,
        mock_organization: Mock,
        mock_organization_member_owner: Mock,
    ):
        """Test organization creation with different profile data."""
        # Arrange different profiles
        profiles_to_test = [
            {
                "id": "profile-1",
                "email": "user1@example.com",
                "displayName": "User One",
            },
            {
                "id": "profile-2",
                "email": "user2@example.com",
                "displayName": None,  # No display name
            },
            {
                "id": "profile-3",
                "email": "user3@company.co.uk",
                "displayName": "Corporate User",
            },
        ]

        service = OrganizationService(mock_prisma)

        for profile_data in profiles_to_test:
            # Create mock profile
            profile = Mock(spec=Profile)
            profile.id = profile_data["id"]
            profile.email = profile_data["email"]
            profile.displayName = profile_data["displayName"]

            # Update mock returns
            mock_prisma.organization.create.return_value = mock_organization
            mock_organization_member_owner.profileId = profile_data["id"]
            mock_prisma.organizationmember.create.return_value = (
                mock_organization_member_owner
            )

            # Act
            result = await service.create_organization(
                organization_create_request, profile
            )

            # Assert
            assert result.organization.id == mock_organization.id
            assert result.role == "owner"

            # Verify correct profile ID was used
            member_call_args = mock_prisma.organizationmember.create.call_args
            member_data = member_call_args[1]["data"]
            assert member_data["profileId"] == profile_data["id"]

    @pytest.mark.asyncio
    async def test_create_organization_response_structure_validation(
        self,
        mock_prisma: Mock,
        mock_profile: Mock,
        organization_create_request: OrganizationCreate,
        mock_organization: Mock,
        mock_organization_member_owner: Mock,
    ):
        """Test that the response structure matches the expected Pydantic models."""
        # Arrange
        mock_prisma.organization.create.return_value = mock_organization
        mock_prisma.organizationmember.create.return_value = (
            mock_organization_member_owner
        )

        # Act
        service = OrganizationService(mock_prisma)
        result = await service.create_organization(
            organization_create_request, mock_profile
        )

        # Assert response structure
        assert hasattr(result, "organization")
        assert hasattr(result, "role")

        # Assert organization structure
        org = result.organization
        assert hasattr(org, "id")
        assert hasattr(org, "name")
        assert hasattr(org, "subscription_tier")
        assert hasattr(org, "created_at")
        assert hasattr(org, "updated_at")

        # Assert data types
        assert isinstance(org.id, str)
        assert isinstance(org.name, str)
        assert isinstance(result.role, str)

    @pytest.mark.asyncio
    async def test_create_organization_subscription_tier_defaults_to_basic(
        self,
        mock_prisma: Mock,
        mock_profile: Mock,
        organization_create_request: OrganizationCreate,
        mock_organization_member_owner: Mock,
    ):
        """Test that new organizations default to basic subscription tier."""
        # Arrange
        mock_organization = Mock()
        mock_organization.id = "test-org-id"
        mock_organization.name = "Test Organization"
        mock_organization.subscriptionTier = "basic"  # This is what we expect to be set
        mock_organization.createdAt = datetime(2024, 1, 15, 9, 0, 0)
        mock_organization.updatedAt = datetime(2024, 1, 15, 9, 0, 0)

        mock_prisma.organization.create.return_value = mock_organization
        mock_prisma.organizationmember.create.return_value = (
            mock_organization_member_owner
        )

        # Act
        service = OrganizationService(mock_prisma)
        result = await service.create_organization(
            organization_create_request, mock_profile
        )

        # Assert subscription tier
        assert result.organization.subscription_tier == "basic"

        # Verify database call used correct subscription tier
        org_call_args = mock_prisma.organization.create.call_args
        org_data = org_call_args[1]["data"]
        assert org_data["subscriptionTier"] == "basic"


class TestOrganizationServiceSwitchOrganization:
    """Test OrganizationService.switch_organization for organization switching."""

    @pytest.fixture
    def mock_session_service(self) -> Mock:
        """Mock SessionService for testing."""
        return Mock()

    @pytest.fixture
    def mock_updated_profile(self) -> Mock:
        """Mock updated Profile after switch."""
        profile = Mock(spec=Profile)
        profile.id = "test-profile-id-123"
        profile.email = "test@example.com"
        profile.displayName = "Test User"
        profile.lastAccessedOrgId = "target-org-id-456"
        return profile

    @pytest.mark.asyncio
    async def test_switch_organization_success(
        self,
        mock_prisma: Mock,
        mock_updated_profile: Mock,
        mock_session_service: Mock,
    ):
        """Test successful organization switch."""
        from src.domains.auth.models import SessionState

        # Mock validation passes
        mock_membership = Mock()
        mock_membership.role = "admin"

        # Mock database operations
        mock_prisma.profile.update.return_value = mock_updated_profile
        mock_prisma.profile.find_unique.return_value = mock_updated_profile

        # Mock session state response
        expected_session_state = SessionState(
            user_id="test-profile-id-123",
            user_email="test@example.com",
            user_display_name="Test User",
            organization_id="target-org-id-456",
            organization_name="Target Organization",
            role="admin",
            subscription_tier="basic",
            active_remittance_id=None,
            organizations=[],
        )

        # Mock SessionService
        with (
            patch(
                "src.domains.organizations.service.validate_organization_access",
                new_callable=AsyncMock,
            ) as mock_validate,
            patch(
                "src.domains.organizations.service.SessionService"
            ) as mock_session_service_class,
        ):

            mock_validate.return_value = mock_membership
            mock_session_instance = Mock()
            mock_session_instance.get_session_state = AsyncMock(
                return_value=expected_session_state
            )
            mock_session_service_class.return_value = mock_session_instance

            # Act
            service = OrganizationService(mock_prisma)
            result = await service.switch_organization(
                "test-profile-id-123", "target-org-id-456"
            )

            # Assert
            assert result == expected_session_state

            # Verify validation was called
            mock_validate.assert_called_once_with(
                "test-profile-id-123", "target-org-id-456", mock_prisma
            )

            # Verify profile update
            mock_prisma.profile.update.assert_called_once_with(
                where={"id": "test-profile-id-123"},
                data={"lastAccessedOrg": {"connect": {"id": "target-org-id-456"}}},
            )

            # Verify profile fetch
            mock_prisma.profile.find_unique.assert_called_once_with(
                where={"id": "test-profile-id-123"}
            )

            # Verify session service usage
            mock_session_service_class.assert_called_once_with(mock_prisma)
            mock_session_instance.get_session_state.assert_called_once_with(
                mock_updated_profile
            )

    @pytest.mark.asyncio
    async def test_switch_organization_access_denied(self, mock_prisma: Mock):
        """Test switch fails when user doesn't have access to organization."""
        from fastapi import HTTPException

        # Mock validation fails
        with patch(
            "src.domains.organizations.service.validate_organization_access",
            new_callable=AsyncMock,
        ) as mock_validate:
            mock_validate.side_effect = HTTPException(
                status_code=403, detail="Access denied to organization"
            )

            # Act & Assert
            service = OrganizationService(mock_prisma)
            with pytest.raises(HTTPException) as exc_info:
                await service.switch_organization(
                    "test-profile-id-123", "target-org-id-456"
                )

            assert exc_info.value.status_code == 403
            assert "Access denied to organization" in exc_info.value.detail

            # Verify profile update was never called
            mock_prisma.profile.update.assert_not_called()

    @pytest.mark.asyncio
    async def test_switch_organization_profile_update_fails(self, mock_prisma: Mock):
        """Test switch fails when profile update fails."""
        from prisma.errors import PrismaError

        # Mock validation passes but update fails
        mock_membership = Mock()

        with patch(
            "src.domains.organizations.service.validate_organization_access",
            new_callable=AsyncMock,
        ) as mock_validate:
            mock_validate.return_value = mock_membership
            mock_prisma.profile.update.side_effect = PrismaError("Update failed")

            # Act & Assert
            service = OrganizationService(mock_prisma)
            with pytest.raises(PrismaError) as exc_info:
                await service.switch_organization(
                    "test-profile-id-123", "target-org-id-456"
                )

            assert "Update failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_switch_organization_profile_not_found_after_update(
        self, mock_prisma: Mock
    ):
        """Test switch fails when profile not found after update."""
        mock_membership = Mock()

        # Mock validation passes, update succeeds, but profile not found
        with patch(
            "src.domains.organizations.service.validate_organization_access",
            new_callable=AsyncMock,
        ) as mock_validate:
            mock_validate.return_value = mock_membership
            mock_prisma.profile.update.return_value = Mock()  # Update succeeds
            mock_prisma.profile.find_unique.return_value = None  # But profile not found

            # Act & Assert
            service = OrganizationService(mock_prisma)
            with pytest.raises(Exception) as exc_info:
                await service.switch_organization(
                    "test-profile-id-123", "target-org-id-456"
                )

            assert "Profile not found after update" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_switch_organization_session_service_error(
        self, mock_prisma: Mock, mock_updated_profile: Mock
    ):
        """Test switch fails when session service fails."""
        from fastapi import HTTPException

        mock_membership = Mock()

        # Mock validation and update succeed, but session service fails
        with (
            patch(
                "src.domains.organizations.service.validate_organization_access"
            ) as mock_validate,
            patch(
                "src.domains.organizations.service.SessionService"
            ) as mock_session_service_class,
        ):

            mock_validate.return_value = mock_membership
            mock_prisma.profile.update.return_value = mock_updated_profile
            mock_prisma.profile.find_unique.return_value = mock_updated_profile

            mock_session_instance = Mock()
            mock_session_instance.get_session_state = AsyncMock(
                side_effect=HTTPException(status_code=500, detail="Session state error")
            )
            mock_session_service_class.return_value = mock_session_instance

            # Act & Assert
            service = OrganizationService(mock_prisma)
            with pytest.raises(HTTPException) as exc_info:
                await service.switch_organization(
                    "test-profile-id-123", "target-org-id-456"
                )

            assert exc_info.value.status_code == 500
            assert "Session state error" in exc_info.value.detail


class TestGetOrganizationMembers:
    """Test organization member retrieval functionality."""

    @pytest.fixture
    def test_org_id(self) -> str:
        """Test organization ID."""
        return "test-org-123"

    @pytest.fixture
    def mock_member_with_profile(self) -> Mock:
        """Mock organization member with profile and inviter details."""
        member = Mock()
        member.profile = Mock()
        member.profile.id = "profile-1"
        member.profile.email = "user1@example.com"
        member.profile.displayName = "John Doe"
        member.role = "admin"
        member.status = "active"
        member.joinedAt = datetime(2024, 1, 15, 10, 30, 0)

        # Mock inviter profile
        member.invitedByProfile = Mock()
        member.invitedByProfile.email = "owner@example.com"

        return member

    @pytest.fixture
    def mock_member_without_inviter(self) -> Mock:
        """Mock organization member without inviter (e.g., organization owner)."""
        member = Mock()
        member.profile = Mock()
        member.profile.id = "profile-2"
        member.profile.email = "owner@example.com"
        member.profile.displayName = "Jane Smith"
        member.role = "owner"
        member.status = "active"
        member.joinedAt = datetime(2024, 1, 1, 9, 0, 0)
        member.invitedByProfile = None

        return member

    @pytest.mark.asyncio
    async def test_get_organization_members_success(
        self,
        mock_prisma: Mock,
        test_org_id: str,
        mock_member_with_profile: Mock,
        mock_member_without_inviter: Mock,
    ):
        """Test successful retrieval of organization members."""
        # Arrange
        mock_prisma.organizationmember.find_many.return_value = [
            mock_member_without_inviter,  # Owner first by join date
            mock_member_with_profile,  # Admin second
        ]

        service = OrganizationService(mock_prisma)

        # Act
        result = await service.get_organization_members(test_org_id)

        # Assert
        assert len(result) == 2

        # Verify first member (owner)
        owner_result = result[0]
        assert owner_result.id == "profile-2"
        assert owner_result.email == "owner@example.com"
        assert owner_result.display_name == "Jane Smith"
        assert owner_result.role == "owner"
        assert owner_result.status == "active"
        assert owner_result.joined_at == "2024-01-01T09:00:00"
        assert owner_result.invited_by_email is None

        # Verify second member (admin)
        admin_result = result[1]
        assert admin_result.id == "profile-1"
        assert admin_result.email == "user1@example.com"
        assert admin_result.display_name == "John Doe"
        assert admin_result.role == "admin"
        assert admin_result.status == "active"
        assert admin_result.joined_at == "2024-01-15T10:30:00"
        assert admin_result.invited_by_email == "owner@example.com"

        # Verify database query
        mock_prisma.organizationmember.find_many.assert_called_once_with(
            where={
                "organizationId": test_org_id,
                "status": MemberStatus.active,
            },
            include={
                "profile": True,
                "invitedByProfile": True,
            },
            order={"joinedAt": "asc"},
        )

    @pytest.mark.asyncio
    async def test_get_organization_members_empty_organization(
        self, mock_prisma: Mock, test_org_id: str
    ):
        """Test handling of organization with no active members."""
        # Arrange
        mock_prisma.organizationmember.find_many.return_value = []

        service = OrganizationService(mock_prisma)

        # Act
        result = await service.get_organization_members(test_org_id)

        # Assert
        assert result == []
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_get_organization_members_member_without_profile(
        self, mock_prisma: Mock, test_org_id: str
    ):
        """Test handling of members without profile relationships."""
        # Arrange - member exists but profile is None
        member_without_profile = Mock()
        member_without_profile.profile = None
        member_without_profile.role = "user"
        member_without_profile.status = "active"

        mock_member_with_profile = Mock()
        mock_member_with_profile.profile = Mock()
        mock_member_with_profile.profile.id = "profile-1"
        mock_member_with_profile.profile.email = "user@example.com"
        mock_member_with_profile.profile.displayName = "Valid User"
        mock_member_with_profile.role = "admin"
        mock_member_with_profile.status = "active"
        mock_member_with_profile.joinedAt = datetime(2024, 1, 15, 10, 30, 0)
        mock_member_with_profile.invitedByProfile = None

        mock_prisma.organizationmember.find_many.return_value = [
            member_without_profile,  # Should be skipped
            mock_member_with_profile,  # Should be included
        ]

        service = OrganizationService(mock_prisma)

        # Act
        result = await service.get_organization_members(test_org_id)

        # Assert - only member with profile should be returned
        assert len(result) == 1
        assert result[0].id == "profile-1"
        assert result[0].email == "user@example.com"

    @pytest.mark.asyncio
    async def test_get_organization_members_handles_none_display_name(
        self, mock_prisma: Mock, test_org_id: str
    ):
        """Test handling of profiles with None display name."""
        # Arrange
        member = Mock()
        member.profile = Mock()
        member.profile.id = "profile-1"
        member.profile.email = "user@example.com"
        member.profile.displayName = None  # No display name
        member.role = "user"
        member.status = "active"
        member.joinedAt = datetime(2024, 1, 15, 10, 30, 0)
        member.invitedByProfile = None

        mock_prisma.organizationmember.find_many.return_value = [member]

        service = OrganizationService(mock_prisma)

        # Act
        result = await service.get_organization_members(test_org_id)

        # Assert
        assert len(result) == 1
        assert result[0].display_name is None

    @pytest.mark.asyncio
    async def test_get_organization_members_handles_none_joined_at(
        self, mock_prisma: Mock, test_org_id: str
    ):
        """Test handling of members with None joinedAt timestamp."""
        # Arrange
        member = Mock()
        member.profile = Mock()
        member.profile.id = "profile-1"
        member.profile.email = "user@example.com"
        member.profile.displayName = "User"
        member.role = "user"
        member.status = "active"
        member.joinedAt = None  # No join timestamp
        member.invitedByProfile = None

        mock_prisma.organizationmember.find_many.return_value = [member]

        service = OrganizationService(mock_prisma)

        # Act
        result = await service.get_organization_members(test_org_id)

        # Assert
        assert len(result) == 1
        assert result[0].joined_at is None
