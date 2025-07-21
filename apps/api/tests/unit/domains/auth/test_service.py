"""
Tests for authentication service functions in src/domains/auth/service.py

Tests the organization access validation and SessionService functions.
"""

from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from prisma.enums import MemberStatus, OrganizationRole
from prisma.models import Profile

from src.domains.auth.models import SessionState
from src.domains.auth.service import SessionService, validate_organization_access


class TestValidateOrganizationAccess:
    """Test organization access validation for different membership scenarios."""

    @pytest.mark.asyncio
    async def test_active_member_access_granted(
        self,
        mock_prisma: Mock,
        mock_organization_member: Mock,
        test_profile_id: str,
        test_organization_id: str,
    ):
        """Test that active member is granted access and returns membership."""
        # Mock successful membership lookup
        mock_prisma.organizationmember.find_first.return_value = (
            mock_organization_member
        )

        result = await validate_organization_access(
            test_profile_id, test_organization_id, mock_prisma
        )

        assert result == mock_organization_member

        # Verify correct query parameters
        call_args = mock_prisma.organizationmember.find_first.call_args
        where_clause = call_args[1]["where"]
        assert where_clause["profileId"] == test_profile_id
        assert where_clause["organizationId"] == test_organization_id
        assert where_clause["status"] == MemberStatus.active

    @pytest.mark.asyncio
    async def test_nonactive_member_access_denied(
        self, mock_prisma: Mock, test_profile_id: str, test_organization_id: str
    ):
        """Test invited/removed members are denied access."""
        # Mock no active membership found (invited/removed members won't match status)
        mock_prisma.organizationmember.find_first.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await validate_organization_access(
                test_profile_id, test_organization_id, mock_prisma
            )

        assert exc_info.value.status_code == 403
        assert "Access denied to organization" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_nonmember_access_denied(
        self, mock_prisma: Mock, test_profile_id: str, test_organization_id: str
    ):
        """Test that users with no membership record are denied access."""
        # Mock no membership found at all
        mock_prisma.organizationmember.find_first.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await validate_organization_access(
                test_profile_id, test_organization_id, mock_prisma
            )

        assert exc_info.value.status_code == 403
        assert "Access denied to organization" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_cross_organization_access_denied(
        self, mock_prisma: Mock, test_profile_id: str
    ):
        """Test that user cannot access different organization they're not member of."""
        different_org_id = "different-org-id-456"

        # Mock no membership found for different organization
        mock_prisma.organizationmember.find_first.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await validate_organization_access(
                test_profile_id, different_org_id, mock_prisma
            )

        assert exc_info.value.status_code == 403
        assert "Access denied to organization" in exc_info.value.detail

        # Verify query used the different org ID
        call_args = mock_prisma.organizationmember.find_first.call_args
        where_clause = call_args[1]["where"]
        assert where_clause["organizationId"] == different_org_id


class TestSessionService:
    """Test SessionService for session state management."""

    @pytest.fixture
    def mock_organization(self) -> Mock:
        """Mock Organization object for testing."""
        org = Mock()
        org.id = "org-1"
        org.name = "Test Organization"
        org.subscriptionTier = "premium"
        return org

    @pytest.fixture
    def mock_organization_2(self) -> Mock:
        """Second mock Organization object for multi-org testing."""
        org = Mock()
        org.id = "org-2"
        org.name = "Second Organization"
        org.subscriptionTier = "basic"
        return org

    @pytest.fixture
    def mock_membership_with_org(self, mock_organization: Mock) -> Mock:
        """Mock OrganizationMember with organization."""
        membership = Mock()
        membership.id = "membership-1"
        membership.profileId = "profile-123"
        membership.organizationId = "org-1"
        membership.role = OrganizationRole.admin
        membership.status = MemberStatus.active
        membership.organization = mock_organization
        return membership

    @pytest.fixture
    def mock_membership_2_with_org(self, mock_organization_2: Mock) -> Mock:
        """Second mock OrganizationMember with organization."""
        membership = Mock()
        membership.id = "membership-2"
        membership.profileId = "profile-123"
        membership.organizationId = "org-2"
        membership.role = OrganizationRole.user
        membership.status = MemberStatus.active
        membership.organization = mock_organization_2
        return membership

    @pytest.fixture
    def test_profile(self) -> Mock:
        """Mock Profile object for testing."""
        profile = Mock(spec=Profile)
        profile.id = "profile-123"
        profile.email = "test@example.com"
        profile.displayName = "Test User"
        profile.lastAccessedOrgId = None
        return profile

    @pytest.fixture
    def test_profile_with_last_org(self) -> Mock:
        """Mock Profile with lastAccessedOrg set."""
        profile = Mock(spec=Profile)
        profile.id = "profile-123"
        profile.email = "test@example.com"
        profile.displayName = "Test User"
        profile.lastAccessedOrgId = "org-2"
        return profile

    @pytest.fixture
    def test_profile_no_display_name(self) -> Mock:
        """Mock Profile without display name."""
        profile = Mock(spec=Profile)
        profile.id = "profile-123"
        profile.email = "test@example.com"
        profile.displayName = None
        profile.lastAccessedOrgId = None
        return profile

    @pytest.mark.asyncio
    async def test_get_session_state_single_organization(
        self,
        mock_prisma: Mock,
        test_profile: Mock,
        mock_membership_with_org: Mock,
    ):
        """Test session state with single organization membership."""
        mock_prisma.organizationmember.find_many.return_value = [
            mock_membership_with_org
        ]

        service = SessionService(mock_prisma)
        result = await service.get_session_state(test_profile)

        assert isinstance(result, SessionState)
        assert result.user_id == "profile-123"
        assert result.user_email == "test@example.com"
        assert result.user_display_name == "Test User"
        assert result.organization_id == "org-1"
        assert result.organization_name == "Test Organization"
        assert result.role == OrganizationRole.admin
        assert result.subscription_tier == "premium"
        assert result.active_remittance_id is None
        assert len(result.organizations) == 1
        assert result.organizations[0].id == "org-1"
        assert result.organizations[0].name == "Test Organization"
        assert result.organizations[0].role == OrganizationRole.admin

        # Verify correct query parameters
        call_args = mock_prisma.organizationmember.find_many.call_args
        assert call_args[1]["where"]["profileId"] == "profile-123"
        assert call_args[1]["where"]["status"] == MemberStatus.active
        assert call_args[1]["include"]["organization"] is True

    @pytest.mark.asyncio
    async def test_get_session_state_multiple_organizations_uses_last_accessed(
        self,
        mock_prisma: Mock,
        test_profile_with_last_org: Mock,
        mock_membership_with_org: Mock,
        mock_membership_2_with_org: Mock,
    ):
        """Test session state with multiple orgs uses lastAccessedOrg preference."""
        mock_prisma.organizationmember.find_many.return_value = [
            mock_membership_with_org,
            mock_membership_2_with_org,
        ]

        service = SessionService(mock_prisma)
        result = await service.get_session_state(test_profile_with_last_org)

        # Should use org-2 as current org (from lastAccessedOrg)
        assert result.organization_id == "org-2"
        assert result.organization_name == "Second Organization"
        assert result.role == OrganizationRole.user
        assert result.subscription_tier == "basic"

        # Should have both organizations in the list
        assert len(result.organizations) == 2
        org_ids = [org.id for org in result.organizations]
        assert "org-1" in org_ids
        assert "org-2" in org_ids

    @pytest.mark.asyncio
    async def test_get_session_state_multiple_organizations_uses_first_as_fallback(
        self,
        mock_prisma: Mock,
        test_profile: Mock,
        mock_membership_with_org: Mock,
        mock_membership_2_with_org: Mock,
    ):
        """Test multiple orgs uses first org when no lastAccessedOrg."""
        mock_prisma.organizationmember.find_many.return_value = [
            mock_membership_with_org,
            mock_membership_2_with_org,
        ]

        service = SessionService(mock_prisma)
        result = await service.get_session_state(test_profile)

        # Should use first org as current org (org-1)
        assert result.organization_id == "org-1"
        assert result.organization_name == "Test Organization"
        assert result.role == OrganizationRole.admin
        assert result.subscription_tier == "premium"

        # Should have both organizations in the list
        assert len(result.organizations) == 2

    @pytest.mark.asyncio
    async def test_get_session_state_no_organizations(
        self,
        mock_prisma: Mock,
        test_profile: Mock,
    ):
        """Test session state when user has no organization memberships."""
        mock_prisma.organizationmember.find_many.return_value = []

        service = SessionService(mock_prisma)
        result = await service.get_session_state(test_profile)

        assert result.user_id == "profile-123"
        assert result.user_email == "test@example.com"
        assert result.user_display_name == "Test User"
        assert result.organization_id is None
        assert result.organization_name is None
        assert result.role is None
        assert result.subscription_tier is None
        assert result.active_remittance_id is None
        assert result.organizations == []

    @pytest.mark.asyncio
    async def test_get_session_state_no_display_name(
        self,
        mock_prisma: Mock,
        test_profile_no_display_name: Mock,
        mock_membership_with_org: Mock,
    ):
        """Test session state when profile has no display name."""
        mock_prisma.organizationmember.find_many.return_value = [
            mock_membership_with_org
        ]

        service = SessionService(mock_prisma)
        result = await service.get_session_state(test_profile_no_display_name)

        assert result.user_display_name is None
        assert result.user_email == "test@example.com"

    @pytest.mark.asyncio
    async def test_get_session_state_membership_without_organization(
        self,
        mock_prisma: Mock,
        test_profile: Mock,
    ):
        """Test session state when membership exists but organization is None."""
        membership_without_org = Mock()
        membership_without_org.organization = None
        mock_prisma.organizationmember.find_many.return_value = [membership_without_org]

        service = SessionService(mock_prisma)
        result = await service.get_session_state(test_profile)

        # Should handle missing organization gracefully
        assert result.organization_id is None
        assert result.organization_name is None
        assert result.role is None
        assert result.subscription_tier is None
        assert result.organizations == []

    @pytest.mark.asyncio
    async def test_get_session_state_organization_missing_subscription_tier(
        self,
        mock_prisma: Mock,
        test_profile: Mock,
        mock_membership_with_org: Mock,
    ):
        """Test session state when organization doesn't have subscriptionTier."""
        # Remove subscriptionTier from organization
        del mock_membership_with_org.organization.subscriptionTier
        mock_prisma.organizationmember.find_many.return_value = [
            mock_membership_with_org
        ]

        service = SessionService(mock_prisma)
        result = await service.get_session_state(test_profile)

        # Should default to 'basic'
        assert result.subscription_tier == "basic"

    @pytest.mark.asyncio
    async def test_get_session_state_database_error(
        self,
        mock_prisma: Mock,
        test_profile: Mock,
    ):
        """Test session state handles database errors gracefully."""
        mock_prisma.organizationmember.find_many.side_effect = Exception(
            "Database connection failed"
        )

        service = SessionService(mock_prisma)

        with pytest.raises(HTTPException) as exc_info:
            await service.get_session_state(test_profile)

        assert exc_info.value.status_code == 500
        assert "Error retrieving session state" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_session_state_lastAccessedOrg_not_in_memberships(
        self,
        mock_prisma: Mock,
        mock_membership_with_org: Mock,
    ):
        """Test when lastAccessedOrg doesn't match any current memberships."""
        # Profile has lastAccessedOrg set to org that user is no longer member of
        profile = Mock(spec=Profile)
        profile.id = "profile-123"
        profile.email = "test@example.com"
        profile.displayName = "Test User"
        profile.lastAccessedOrgId = "org-nonexistent"

        mock_prisma.organizationmember.find_many.return_value = [
            mock_membership_with_org
        ]

        service = SessionService(mock_prisma)
        result = await service.get_session_state(profile)

        # Should fall back to first available org
        assert result.organization_id == "org-1"
        assert result.organization_name == "Test Organization"
