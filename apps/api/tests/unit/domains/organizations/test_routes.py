"""
Tests for organization routes in src/domains/organizations/routes.py

Tests the organization switch endpoint and HTTP handling.
"""

from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException
from prisma.models import Profile

from src.domains.auth.models import SessionState


class TestOrganizationSwitchRoute:
    """Test organization switch route functionality."""

    @pytest.fixture
    def mock_profile(self) -> Mock:
        """Mock Profile for authenticated user."""
        profile = Mock(spec=Profile)
        profile.id = "test-profile-id-123"
        profile.email = "test@example.com"
        profile.displayName = "Test User"
        return profile

    @pytest.fixture
    def mock_session_state(self) -> SessionState:
        """Mock SessionState response."""
        return SessionState(
            user_id="test-profile-id-123",
            user_email="test@example.com",
            user_display_name="Test User",
            organization_id="target-org-id-456",
            organization_name="Target Organization",
            role="admin",
            subscription_tier="premium",
            active_remittance_id=None,
            organizations=[],
        )

    @pytest.mark.asyncio
    async def test_switch_organization_success(
        self,
        mock_profile: Mock,
        mock_session_state: SessionState,
    ):
        """Test successful organization switch via POST endpoint."""
        from src.domains.organizations.routes import switch_organization

        org_id = uuid4()

        # Mock dependencies
        with (
            patch(
                "src.domains.organizations.routes.get_current_profile"
            ) as mock_get_profile,
            patch("src.domains.organizations.routes.get_db") as mock_get_db,
            patch(
                "src.domains.organizations.routes.OrganizationService"
            ) as mock_service_class,
        ):

            mock_get_profile.return_value = mock_profile
            mock_db = Mock()
            mock_get_db.return_value = mock_db

            mock_service_instance = Mock()
            mock_service_instance.switch_organization = AsyncMock(
                return_value=mock_session_state
            )
            mock_service_class.return_value = mock_service_instance

            # Act
            result = await switch_organization(
                org_id=org_id, profile=mock_profile, db=mock_db
            )

            # Assert
            assert result == mock_session_state

            # Verify service was called correctly
            mock_service_class.assert_called_once_with(mock_db)
            mock_service_instance.switch_organization.assert_called_once_with(
                mock_profile.id, str(org_id)
            )

    @pytest.mark.asyncio
    async def test_switch_organization_access_denied(self, mock_profile: Mock):
        """Test organization switch when access is denied."""
        from src.domains.organizations.routes import switch_organization

        org_id = uuid4()

        # Mock dependencies - service raises HTTPException
        with (
            patch(
                "src.domains.organizations.routes.get_current_profile"
            ) as mock_get_profile,
            patch("src.domains.organizations.routes.get_db") as mock_get_db,
            patch(
                "src.domains.organizations.routes.OrganizationService"
            ) as mock_service_class,
        ):

            mock_get_profile.return_value = mock_profile
            mock_db = Mock()
            mock_get_db.return_value = mock_db

            mock_service_instance = Mock()
            mock_service_instance.switch_organization = AsyncMock(
                side_effect=HTTPException(
                    status_code=403, detail="Access denied to organization"
                )
            )
            mock_service_class.return_value = mock_service_instance

            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                await switch_organization(
                    org_id=org_id, profile=mock_profile, db=mock_db
                )

            assert exc_info.value.status_code == 403
            assert "Access denied to organization" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_switch_organization_database_error(self, mock_profile: Mock):
        """Test organization switch when database error occurs."""
        from prisma.errors import PrismaError

        from src.domains.organizations.routes import switch_organization

        org_id = uuid4()

        # Mock dependencies - service raises database error
        with (
            patch(
                "src.domains.organizations.routes.get_current_profile"
            ) as mock_get_profile,
            patch("src.domains.organizations.routes.get_db") as mock_get_db,
            patch(
                "src.domains.organizations.routes.OrganizationService"
            ) as mock_service_class,
        ):

            mock_get_profile.return_value = mock_profile
            mock_db = Mock()
            mock_get_db.return_value = mock_db

            mock_service_instance = Mock()
            mock_service_instance.switch_organization = AsyncMock(
                side_effect=PrismaError("Database connection failed")
            )
            mock_service_class.return_value = mock_service_instance

            # Act & Assert
            with pytest.raises(PrismaError) as exc_info:
                await switch_organization(
                    org_id=org_id, profile=mock_profile, db=mock_db
                )

            assert "Database connection failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_switch_organization_converts_uuid_to_string(
        self, mock_profile: Mock, mock_session_state: SessionState
    ):
        """Test that UUID parameter is converted to string for service call."""
        from src.domains.organizations.routes import switch_organization

        org_id = uuid4()

        # Mock dependencies
        with (
            patch(
                "src.domains.organizations.routes.get_current_profile"
            ) as mock_get_profile,
            patch("src.domains.organizations.routes.get_db") as mock_get_db,
            patch(
                "src.domains.organizations.routes.OrganizationService"
            ) as mock_service_class,
        ):

            mock_get_profile.return_value = mock_profile
            mock_db = Mock()
            mock_get_db.return_value = mock_db

            mock_service_instance = Mock()
            mock_service_instance.switch_organization = AsyncMock(
                return_value=mock_session_state
            )
            mock_service_class.return_value = mock_service_instance

            # Act
            await switch_organization(org_id=org_id, profile=mock_profile, db=mock_db)

            # Assert - verify UUID was converted to string
            mock_service_instance.switch_organization.assert_called_once_with(
                mock_profile.id, str(org_id)  # UUID should be converted to string
            )

            # Verify the call used string, not UUID object
            call_args = mock_service_instance.switch_organization.call_args[0]
            assert isinstance(call_args[1], str)
            assert call_args[1] == str(org_id)

    @pytest.mark.asyncio
    async def test_switch_organization_profile_id_extraction(
        self, mock_session_state: SessionState
    ):
        """Test that profile.id is correctly extracted and passed to service."""
        from src.domains.organizations.routes import switch_organization

        # Create profile with specific ID to verify extraction
        profile = Mock(spec=Profile)
        profile.id = "specific-profile-id-789"
        profile.email = "test@example.com"

        org_id = uuid4()

        # Mock dependencies
        with (
            patch(
                "src.domains.organizations.routes.get_current_profile"
            ) as mock_get_profile,
            patch("src.domains.organizations.routes.get_db") as mock_get_db,
            patch(
                "src.domains.organizations.routes.OrganizationService"
            ) as mock_service_class,
        ):

            mock_get_profile.return_value = profile
            mock_db = Mock()
            mock_get_db.return_value = mock_db

            mock_service_instance = Mock()
            mock_service_instance.switch_organization = AsyncMock(
                return_value=mock_session_state
            )
            mock_service_class.return_value = mock_service_instance

            # Act
            await switch_organization(org_id=org_id, profile=profile, db=mock_db)

            # Assert - verify correct profile ID was passed
            mock_service_instance.switch_organization.assert_called_once_with(
                "specific-profile-id-789", str(org_id)
            )

    @pytest.mark.asyncio
    async def test_switch_organization_returns_session_state_model(
        self, mock_profile: Mock, mock_session_state: SessionState
    ):
        """Test that route returns SessionState model with correct structure."""
        from src.domains.organizations.routes import switch_organization

        org_id = uuid4()

        # Mock dependencies
        with (
            patch(
                "src.domains.organizations.routes.get_current_profile"
            ) as mock_get_profile,
            patch("src.domains.organizations.routes.get_db") as mock_get_db,
            patch(
                "src.domains.organizations.routes.OrganizationService"
            ) as mock_service_class,
        ):

            mock_get_profile.return_value = mock_profile
            mock_db = Mock()
            mock_get_db.return_value = mock_db

            mock_service_instance = Mock()
            mock_service_instance.switch_organization = AsyncMock(
                return_value=mock_session_state
            )
            mock_service_class.return_value = mock_service_instance

            # Act
            result = await switch_organization(
                org_id=org_id, profile=mock_profile, db=mock_db
            )

            # Assert response structure
            assert isinstance(result, SessionState)
            assert result.user_id == "test-profile-id-123"
            assert result.user_email == "test@example.com"
            assert result.organization_id == "target-org-id-456"
            assert result.organization_name == "Target Organization"
            assert result.role == "admin"
            assert result.subscription_tier == "premium"
            assert result.active_remittance_id is None
            assert isinstance(result.organizations, list)


class TestGetOrganizationMembersRoute:
    """Test organization members endpoint functionality."""

    @pytest.fixture
    def mock_profile(self) -> Mock:
        """Mock Profile for authenticated user."""
        profile = Mock(spec=Profile)
        profile.id = "test-profile-id-123"
        profile.email = "admin@example.com"
        profile.displayName = "Admin User"
        return profile

    @pytest.fixture
    def mock_membership(self) -> Mock:
        """Mock OrganizationMember for authorization."""
        from prisma.models import OrganizationMember

        membership = Mock(spec=OrganizationMember)
        membership.id = "membership-123"
        membership.role = "admin"
        membership.status = "active"
        return membership

    @pytest.fixture
    def mock_member_responses(self) -> list:
        """Mock list of OrganizationMemberResponse objects."""
        from src.domains.organizations.models import OrganizationMemberResponse

        return [
            OrganizationMemberResponse(
                id="profile-1",
                email="owner@example.com",
                display_name="Jane Smith",
                role="owner",
                status="active",
                joined_at="2024-01-01T09:00:00",
                invited_by_email=None,
            ),
            OrganizationMemberResponse(
                id="profile-2",
                email="admin@example.com",
                display_name="Admin User",
                role="admin",
                status="active",
                joined_at="2024-01-15T10:30:00",
                invited_by_email="owner@example.com",
            ),
        ]

    @pytest.mark.asyncio
    async def test_get_organization_members_success_with_admin(
        self,
        mock_profile: Mock,
        mock_membership: Mock,
        mock_member_responses: list,
    ):
        """Test successful member retrieval with admin user."""
        from src.domains.organizations.routes import get_organization_members

        org_id = uuid4()

        # Mock dependencies
        with (
            patch(
                "src.domains.organizations.routes.require_permission"
            ) as mock_require_permission,
            patch("src.domains.organizations.routes.get_db") as mock_get_db,
            patch(
                "src.domains.organizations.routes.OrganizationService"
            ) as mock_service_class,
        ):

            # Mock permission dependency
            mock_permission_dependency = AsyncMock(return_value=mock_membership)
            mock_require_permission.return_value = mock_permission_dependency

            mock_db = Mock()
            mock_get_db.return_value = mock_db

            mock_service_instance = Mock()
            mock_service_instance.get_organization_members = AsyncMock(
                return_value=mock_member_responses
            )
            mock_service_class.return_value = mock_service_instance

            # Act
            result = await get_organization_members(
                org_id=org_id,
                membership=mock_membership,
                db=mock_db,
            )

            # Assert
            assert result == mock_member_responses
            assert len(result) == 2

            # Verify service was called correctly
            mock_service_class.assert_called_once_with(mock_db)
            mock_service_instance.get_organization_members.assert_called_once_with(
                str(org_id)
            )

    @pytest.mark.asyncio
    async def test_get_organization_members_success_with_owner(
        self,
        mock_profile: Mock,
        mock_member_responses: list,
    ):
        """Test successful member retrieval with owner user."""
        from prisma.models import OrganizationMember

        from src.domains.organizations.routes import get_organization_members

        # Mock owner membership
        owner_membership = Mock(spec=OrganizationMember)
        owner_membership.role = "owner"
        owner_membership.status = "active"

        org_id = uuid4()

        # Mock dependencies
        with (
            patch(
                "src.domains.organizations.routes.require_permission"
            ) as mock_require_permission,
            patch("src.domains.organizations.routes.get_db") as mock_get_db,
            patch(
                "src.domains.organizations.routes.OrganizationService"
            ) as mock_service_class,
        ):

            # Mock permission dependency
            mock_permission_dependency = AsyncMock(return_value=owner_membership)
            mock_require_permission.return_value = mock_permission_dependency

            mock_db = Mock()
            mock_get_db.return_value = mock_db

            mock_service_instance = Mock()
            mock_service_instance.get_organization_members = AsyncMock(
                return_value=mock_member_responses
            )
            mock_service_class.return_value = mock_service_instance

            # Act
            result = await get_organization_members(
                org_id=org_id,
                membership=owner_membership,
                db=mock_db,
            )

            # Assert
            assert result == mock_member_responses

    @pytest.mark.asyncio
    async def test_get_organization_members_success_with_auditor(
        self,
        mock_profile: Mock,
        mock_member_responses: list,
    ):
        """Test successful member retrieval with auditor user."""
        from prisma.models import OrganizationMember

        from src.domains.organizations.routes import get_organization_members

        # Mock auditor membership
        auditor_membership = Mock(spec=OrganizationMember)
        auditor_membership.role = "auditor"
        auditor_membership.status = "active"

        org_id = uuid4()

        # Mock dependencies
        with (
            patch(
                "src.domains.organizations.routes.require_permission"
            ) as mock_require_permission,
            patch("src.domains.organizations.routes.get_db") as mock_get_db,
            patch(
                "src.domains.organizations.routes.OrganizationService"
            ) as mock_service_class,
        ):

            # Mock permission dependency
            mock_permission_dependency = AsyncMock(return_value=auditor_membership)
            mock_require_permission.return_value = mock_permission_dependency

            mock_db = Mock()
            mock_get_db.return_value = mock_db

            mock_service_instance = Mock()
            mock_service_instance.get_organization_members = AsyncMock(
                return_value=mock_member_responses
            )
            mock_service_class.return_value = mock_service_instance

            # Act
            result = await get_organization_members(
                org_id=org_id,
                membership=auditor_membership,
                db=mock_db,
            )

            # Assert
            assert result == mock_member_responses

    @pytest.mark.asyncio
    async def test_get_organization_members_permission_check_integration(
        self, mock_profile: Mock
    ):
        """Test permission checking integration with require_permission dependency."""
        from src.shared.permissions import Permission, require_permission

        org_id = uuid4()

        # Mock a user membership that lacks VIEW_MEMBERS permission
        user_membership = Mock()
        user_membership.role = "user"
        user_membership.status = "active"
        user_membership.organizationId = str(org_id)

        # Mock database to return user membership
        mock_db = Mock()
        mock_db.organizationmember.find_first = AsyncMock(return_value=user_membership)

        # Test the actual permission dependency
        permission_dependency = require_permission(Permission.VIEW_MEMBERS)

        # Act & Assert - this should raise HTTPException for insufficient permissions
        with pytest.raises(HTTPException) as exc_info:
            await permission_dependency(
                org_id=org_id,
                profile=mock_profile,
                db=mock_db,
            )

        assert exc_info.value.status_code == 403
        assert "Insufficient permissions" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_organization_members_empty_result(self, mock_membership: Mock):
        """Test handling of organization with no members."""
        from src.domains.organizations.routes import get_organization_members

        org_id = uuid4()

        # Mock dependencies
        with (
            patch(
                "src.domains.organizations.routes.require_permission"
            ) as mock_require_permission,
            patch("src.domains.organizations.routes.get_db") as mock_get_db,
            patch(
                "src.domains.organizations.routes.OrganizationService"
            ) as mock_service_class,
        ):

            # Mock permission dependency
            mock_permission_dependency = AsyncMock(return_value=mock_membership)
            mock_require_permission.return_value = mock_permission_dependency

            mock_db = Mock()
            mock_get_db.return_value = mock_db

            mock_service_instance = Mock()
            mock_service_instance.get_organization_members = AsyncMock(
                return_value=[]  # Empty list
            )
            mock_service_class.return_value = mock_service_instance

            # Act
            result = await get_organization_members(
                org_id=org_id,
                membership=mock_membership,
                db=mock_db,
            )

            # Assert
            assert result == []
            assert len(result) == 0

    @pytest.mark.asyncio
    async def test_get_organization_members_uuid_conversion(
        self, mock_membership: Mock, mock_member_responses: list
    ):
        """Test that UUID parameter is converted to string for service call."""
        from src.domains.organizations.routes import get_organization_members

        org_id = uuid4()

        # Mock dependencies
        with (
            patch(
                "src.domains.organizations.routes.require_permission"
            ) as mock_require_permission,
            patch("src.domains.organizations.routes.get_db") as mock_get_db,
            patch(
                "src.domains.organizations.routes.OrganizationService"
            ) as mock_service_class,
        ):

            # Mock permission dependency
            mock_permission_dependency = AsyncMock(return_value=mock_membership)
            mock_require_permission.return_value = mock_permission_dependency

            mock_db = Mock()
            mock_get_db.return_value = mock_db

            mock_service_instance = Mock()
            mock_service_instance.get_organization_members = AsyncMock(
                return_value=mock_member_responses
            )
            mock_service_class.return_value = mock_service_instance

            # Act
            await get_organization_members(
                org_id=org_id,
                membership=mock_membership,
                db=mock_db,
            )

            # Assert - verify UUID was converted to string
            mock_service_instance.get_organization_members.assert_called_once_with(
                str(org_id)  # UUID should be converted to string
            )

            # Verify the call used string, not UUID object
            call_args = mock_service_instance.get_organization_members.call_args[0]
            assert isinstance(call_args[0], str)
            assert call_args[0] == str(org_id)

    @pytest.mark.asyncio
    async def test_get_organization_members_response_structure(
        self, mock_membership: Mock, mock_member_responses: list
    ):
        """Test route returns List[OrganizationMemberResponse] structure."""
        from src.domains.organizations.routes import get_organization_members

        org_id = uuid4()

        # Mock dependencies
        with (
            patch(
                "src.domains.organizations.routes.require_permission"
            ) as mock_require_permission,
            patch("src.domains.organizations.routes.get_db") as mock_get_db,
            patch(
                "src.domains.organizations.routes.OrganizationService"
            ) as mock_service_class,
        ):

            # Mock permission dependency
            mock_permission_dependency = AsyncMock(return_value=mock_membership)
            mock_require_permission.return_value = mock_permission_dependency

            mock_db = Mock()
            mock_get_db.return_value = mock_db

            mock_service_instance = Mock()
            mock_service_instance.get_organization_members = AsyncMock(
                return_value=mock_member_responses
            )
            mock_service_class.return_value = mock_service_instance

            # Act
            result = await get_organization_members(
                org_id=org_id,
                membership=mock_membership,
                db=mock_db,
            )

            # Assert response structure
            assert isinstance(result, list)
            assert len(result) == 2

            # Verify first member structure
            first_member = result[0]
            assert hasattr(first_member, "id")
            assert hasattr(first_member, "email")
            assert hasattr(first_member, "display_name")
            assert hasattr(first_member, "role")
            assert hasattr(first_member, "status")
            assert hasattr(first_member, "joined_at")
            assert hasattr(first_member, "invited_by_email")

            assert first_member.id == "profile-1"
            assert first_member.email == "owner@example.com"
            assert first_member.role == "owner"
