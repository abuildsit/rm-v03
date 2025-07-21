"""
Test fixtures and factories for organization-related test data.
"""

from datetime import datetime
from typing import Any, Dict
from unittest.mock import Mock

import pytest
from prisma.enums import MemberStatus, OrganizationRole
from prisma.models import Organization, OrganizationMember


@pytest.fixture
def mock_organization() -> Mock:
    """Mock Organization object for testing."""
    org = Mock(spec=Organization)
    org.id = "test-org-id-123"
    org.name = "Test Organization"
    org.subscriptionTier = "basic"
    org.createdAt = datetime(2024, 1, 15, 9, 0, 0)
    org.updatedAt = datetime(2024, 1, 15, 9, 0, 0)
    return org


@pytest.fixture
def mock_organization_premium() -> Mock:
    """Mock Organization object with premium subscription for testing."""
    org = Mock(spec=Organization)
    org.id = "test-org-premium-456"
    org.name = "Premium Organization"
    org.subscriptionTier = "premium"
    org.createdAt = datetime(2024, 1, 15, 9, 0, 0)
    org.updatedAt = datetime(2024, 1, 15, 9, 0, 0)
    return org


@pytest.fixture
def mock_organization_member_owner() -> Mock:
    """Mock OrganizationMember with owner role for testing."""
    member = Mock(spec=OrganizationMember)
    member.id = "test-member-owner-123"
    member.profileId = "test-profile-id-123"
    member.organizationId = "test-org-id-123"
    member.role = OrganizationRole.owner
    member.status = MemberStatus.active
    member.joinedAt = datetime(2024, 1, 15, 9, 0, 0)
    member.createdAt = datetime(2024, 1, 15, 9, 0, 0)
    return member


@pytest.fixture
def mock_organization_member_admin() -> Mock:
    """Mock OrganizationMember with admin role for testing."""
    member = Mock(spec=OrganizationMember)
    member.id = "test-member-admin-456"
    member.profileId = "test-profile-id-456"
    member.organizationId = "test-org-id-123"
    member.role = OrganizationRole.admin
    member.status = MemberStatus.active
    member.joinedAt = datetime(2024, 1, 16, 9, 0, 0)
    member.createdAt = datetime(2024, 1, 16, 9, 0, 0)
    return member


@pytest.fixture
def organization_create_data() -> Dict[str, Any]:
    """Valid organization creation data for testing."""
    return {"name": "Test Organization"}


@pytest.fixture
def organization_create_data_with_special_chars() -> Dict[str, Any]:
    """Organization creation data with special characters for testing."""
    return {"name": "Acme Corp & Associates - Ltd."}


@pytest.fixture
def organization_create_data_empty_name() -> Dict[str, Any]:
    """Organization creation data with empty name for testing validation."""
    return {"name": ""}


@pytest.fixture
def organization_create_data_long_name() -> Dict[str, Any]:
    """Organization creation data with very long name for testing limits."""
    return {"name": "A" * 255}  # Very long organization name


class OrganizationTestData:
    """Helper class for generating consistent organization test data."""

    @staticmethod
    def organization_ids() -> Dict[str, str]:
        """Standard test organization IDs."""
        return {
            "default": "test-org-id-123",
            "premium": "test-org-premium-456",
            "different": "different-org-id-789",
        }

    @staticmethod
    def organization_names() -> Dict[str, str]:
        """Standard test organization names."""
        return {
            "default": "Test Organization",
            "premium": "Premium Organization",
            "special_chars": "Acme Corp & Associates - Ltd.",
            "unicode": "Тест Организация 测试组织",
        }

    @staticmethod
    def subscription_tiers() -> list[str]:
        """Available subscription tiers."""
        return ["basic", "premium", "enterprise"]

    @staticmethod
    def organization_roles() -> list[OrganizationRole]:
        """Available organization roles."""
        return [
            OrganizationRole.owner,
            OrganizationRole.admin,
            OrganizationRole.user,
            OrganizationRole.auditor,
        ]

    @staticmethod
    def member_statuses() -> list[MemberStatus]:
        """Available member statuses."""
        return [
            MemberStatus.active,
            MemberStatus.invited,
            MemberStatus.removed,
        ]
