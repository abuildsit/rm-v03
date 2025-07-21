"""
Test fixtures and factories for authentication-related test data.
"""

from typing import Any, Dict
from unittest.mock import Mock

import pytest
from prisma.enums import MemberStatus, OrganizationRole
from prisma.models import AuthLink, OrganizationMember, Profile


@pytest.fixture
def mock_profile() -> Mock:
    """Mock Profile object for testing."""
    profile = Mock(spec=Profile)
    profile.id = "test-profile-id-123"
    profile.email = "test@example.com"
    profile.displayName = "Test User"
    profile.lastAccessedOrgId = "42f929b1-8fdb-45b1-a7cf-34fae2314561"
    return profile


@pytest.fixture
def mock_auth_link() -> Mock:
    """Mock AuthLink object for testing."""
    auth_link = Mock(spec=AuthLink)
    auth_link.id = "test-auth-link-id"
    auth_link.authId = "test-user-id-123"
    auth_link.profileId = "test-profile-id-123"
    auth_link.provider = "supabase"
    auth_link.providerUserId = "test-user-id-123"
    return auth_link


@pytest.fixture
def mock_auth_link_with_profile(mock_auth_link: Mock, mock_profile: Mock) -> Mock:
    """Mock AuthLink with associated Profile."""
    mock_auth_link.profile = mock_profile
    return mock_auth_link


@pytest.fixture
def mock_organization_member() -> Mock:
    """Mock OrganizationMember object for testing."""
    member = Mock(spec=OrganizationMember)
    member.id = "test-member-id"
    member.profileId = "test-profile-id-123"
    member.organizationId = "42f929b1-8fdb-45b1-a7cf-34fae2314561"
    member.role = OrganizationRole.admin
    member.status = MemberStatus.active
    return member


@pytest.fixture
def inactive_organization_member(mock_organization_member: Mock) -> Mock:
    """Mock inactive OrganizationMember for testing access denial."""
    mock_organization_member.status = MemberStatus.invited
    return mock_organization_member


class AuthTestData:
    """Helper class for generating consistent auth test data."""

    @staticmethod
    def valid_jwt_payload(auth_id: str = "test-user-id-123") -> Dict[str, Any]:
        """Generate valid JWT payload."""
        return {
            "sub": auth_id,
            "email": "test@example.com",
            "aud": "authenticated",
            "iss": "supabase",
        }

    @staticmethod
    def invalid_jwt_payload() -> Dict[str, Any]:
        """Generate invalid JWT payload missing required claims."""
        return {"invalid": "payload", "missing": "sub_claim"}
