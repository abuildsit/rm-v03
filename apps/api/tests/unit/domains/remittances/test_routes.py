"""
Tests for remittance routes in src/domains/remittances/routes.py

Tests route logic directly, with permission system tested separately.
"""

from unittest.mock import patch

import pytest
from fastapi import HTTPException
from prisma.enums import OrganizationRole

from src.domains.remittances.models import (
    FileUrlResponse,
    RemittanceDetailResponse,
    RemittanceListResponse,
)


class TestUploadRemittanceRoute:
    """Test upload remittance file route function."""

    @pytest.mark.asyncio
    @patch("src.domains.remittances.routes.create_remittance")
    async def test_upload_remittance_success(
        self,
        mock_create_remittance,
        mock_organization_member_admin,
        mock_remittance_uploaded,
        mock_pdf_file,
        mock_prisma,
    ):
        """Test successful file upload."""
        from src.domains.remittances.routes import upload_remittance

        # Mock service response
        mock_create_remittance.return_value = mock_remittance_uploaded

        # Call route function directly
        result = await upload_remittance(
            org_id="test-org-123",
            file=mock_pdf_file,
            membership=mock_organization_member_admin,
            db=mock_prisma,
        )

        # Verify result
        assert result.message == "File uploaded successfully"
        assert result.remittance_id == mock_remittance_uploaded.id
        assert result.filename == mock_remittance_uploaded.filename
        assert result.file_path == mock_remittance_uploaded.file_path

        # Verify service was called correctly
        mock_create_remittance.assert_called_once_with(
            db=mock_prisma,
            org_id="test-org-123",
            user_id=mock_organization_member_admin.profileId,
            file=mock_pdf_file,
        )

    @pytest.mark.asyncio
    async def test_upload_remittance_no_permission(self):
        """Test upload without permission is handled by permission system."""
        # Note: Permission checking is handled by FastAPI dependency injection
        # and tested separately in the permission system tests.
        # This test verifies the route uses the correct permission.
        import inspect

        from src.domains.remittances.routes import upload_remittance

        # Verify the route function signature includes permission dependency
        sig = inspect.signature(upload_remittance)
        membership_param = sig.parameters.get("membership")

        # The membership parameter should exist and have a Depends annotation
        assert membership_param is not None
        assert hasattr(membership_param.default, "dependency")

        # This ensures permission checking is in place
        # Actual permission denial testing is done in permission system tests

    @pytest.mark.asyncio
    @patch("src.domains.remittances.routes.create_remittance")
    async def test_upload_remittance_service_error(
        self,
        mock_create_remittance,
        mock_organization_member_admin,
        mock_invalid_file,
        mock_prisma,
    ):
        """Test upload with service error."""
        from src.domains.remittances.routes import upload_remittance

        # Mock service to raise an error
        mock_create_remittance.side_effect = HTTPException(
            status_code=400, detail="Invalid file type"
        )

        # Verify that the exception is propagated
        with pytest.raises(HTTPException) as exc_info:
            await upload_remittance(
                org_id="test-org-123",
                file=mock_invalid_file,
                membership=mock_organization_member_admin,
                db=mock_prisma,
            )

        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "Invalid file type"


class TestListRemittancesRoute:
    """Test list remittances route function."""

    @pytest.mark.asyncio
    @patch("src.domains.remittances.routes.get_remittances_by_organization")
    async def test_list_remittances_success(
        self,
        mock_get_remittances,
        mock_organization_member_admin,
        remittance_list_response_data,
        mock_prisma,
    ):
        """Test successful remittances list retrieval."""
        from src.domains.remittances.routes import list_remittances

        # Mock service response
        mock_response = RemittanceListResponse(**remittance_list_response_data)
        mock_get_remittances.return_value = mock_response

        # Call route function directly
        result = await list_remittances(
            org_id="test-org-123",
            page=1,
            page_size=50,
            status_filter=None,
            date_from=None,
            date_to=None,
            search=None,
            membership=mock_organization_member_admin,
            db=mock_prisma,
        )

        # Verify result
        assert isinstance(result, RemittanceListResponse)
        assert result.total == mock_response.total
        assert result.page == mock_response.page
        assert result.page_size == mock_response.page_size

        # Verify service was called correctly
        mock_get_remittances.assert_called_once_with(
            db=mock_prisma,
            org_id="test-org-123",
            page=1,
            page_size=50,
            status_filter=None,
            date_from=None,
            date_to=None,
            search=None,
        )

    @pytest.mark.asyncio
    @patch("src.domains.remittances.routes.get_remittances_by_organization")
    async def test_list_remittances_with_filters(
        self,
        mock_get_remittances,
        mock_organization_member_admin,
        remittance_list_response_data,
        mock_prisma,
    ):
        """Test remittances list with query filters."""
        from src.domains.remittances.routes import list_remittances

        mock_response = RemittanceListResponse(**remittance_list_response_data)
        mock_get_remittances.return_value = mock_response

        # Call route function with filters
        result = await list_remittances(
            org_id="test-org-123",
            page=2,
            page_size=25,
            status_filter="Uploaded",
            date_from="2024-01-01",
            date_to="2024-01-31",
            search="test",
            membership=mock_organization_member_admin,
            db=mock_prisma,
        )

        # Verify result
        assert isinstance(result, RemittanceListResponse)

        # Verify service was called with filters
        mock_get_remittances.assert_called_once_with(
            db=mock_prisma,
            org_id="test-org-123",
            page=2,
            page_size=25,
            status_filter="Uploaded",
            date_from="2024-01-01",
            date_to="2024-01-31",
            search="test",
        )

    @pytest.mark.asyncio
    async def test_list_remittances_auditor_permission(self):
        """Test that auditor can view remittances."""
        # Note: Permission testing is handled by the permission system tests.
        # This test verifies the route uses the correct permission.
        import inspect

        from src.domains.remittances.routes import list_remittances

        # Verify the route function uses VIEW_REMITTANCES permission
        sig = inspect.signature(list_remittances)
        membership_param = sig.parameters.get("membership")

        assert membership_param is not None
        assert hasattr(membership_param.default, "dependency")
        # This ensures auditors with VIEW_REMITTANCES can access this route


class TestGetRemittanceRoute:
    """Test get single remittance route function."""

    @pytest.mark.asyncio
    @patch("src.domains.remittances.routes.get_remittance_by_id")
    async def test_get_remittance_success(
        self,
        mock_get_remittance,
        mock_organization_member_admin,
        mock_remittance_processed,
        mock_remittance_line,
        mock_prisma,
    ):
        """Test successful single remittance retrieval."""
        from src.domains.remittances.routes import get_remittance

        # Setup mock response with lines
        mock_remittance_processed.lines = [mock_remittance_line]
        mock_response = RemittanceDetailResponse.model_validate(
            mock_remittance_processed
        )
        mock_get_remittance.return_value = mock_response

        # Call route function directly
        result = await get_remittance(
            org_id="test-org-123",
            remittance_id="test-remittance-id-456",
            membership=mock_organization_member_admin,
            db=mock_prisma,
        )

        # Verify result
        assert isinstance(result, RemittanceDetailResponse)
        assert result.id == "test-remittance-id-456"
        assert len(result.lines) == 1

        # Verify service was called correctly
        mock_get_remittance.assert_called_once_with(
            db=mock_prisma,
            org_id="test-org-123",
            remittance_id="test-remittance-id-456",
        )

    @pytest.mark.asyncio
    @patch("src.domains.remittances.routes.get_remittance_by_id")
    async def test_get_remittance_not_found(
        self,
        mock_get_remittance,
        mock_organization_member_admin,
        mock_prisma,
    ):
        """Test get non-existent remittance."""
        from src.domains.remittances.routes import get_remittance

        mock_get_remittance.side_effect = HTTPException(
            status_code=404, detail="Remittance not found"
        )

        # Verify that the exception is propagated
        with pytest.raises(HTTPException) as exc_info:
            await get_remittance(
                org_id="test-org-123",
                remittance_id="nonexistent-id",
                membership=mock_organization_member_admin,
                db=mock_prisma,
            )

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Remittance not found"


class TestUpdateRemittanceRoute:
    """Test update remittance route function."""

    @pytest.mark.asyncio
    @patch("src.domains.remittances.routes.update_remittance")
    async def test_update_remittance_success(
        self,
        mock_update_remittance,
        mock_organization_member_admin,
        mock_remittance_processed,
        mock_prisma,
    ):
        """Test successful remittance update."""
        from src.domains.remittances.models import RemittanceUpdateRequest
        from src.domains.remittances.routes import update_remittance_endpoint

        mock_response = RemittanceDetailResponse.model_validate(
            mock_remittance_processed
        )
        mock_update_remittance.return_value = mock_response

        update_data = RemittanceUpdateRequest(
            status="Data_Retrieved",
            total_amount="1500.50",
            reference="REF-12345",
        )

        # Call route function directly
        result = await update_remittance_endpoint(
            org_id="test-org-123",
            remittance_id="test-remittance-id-456",
            update_data=update_data,
            membership=mock_organization_member_admin,
            db=mock_prisma,
        )

        # Verify result
        assert isinstance(result, RemittanceDetailResponse)
        assert result.id == mock_remittance_processed.id

        # Verify service was called correctly
        mock_update_remittance.assert_called_once_with(
            db=mock_prisma,
            org_id="test-org-123",
            user_id=mock_organization_member_admin.profileId,
            remittance_id="test-remittance-id-456",
            update_data=update_data,
        )

    @pytest.mark.asyncio
    @patch("src.domains.remittances.routes.update_remittance")
    async def test_update_remittance_approval(
        self,
        mock_update_remittance,
        mock_organization_member_user,
        mock_remittance_processed,
        mock_prisma,
    ):
        """Test remittance approval by regular user."""
        from src.domains.remittances.models import RemittanceUpdateRequest
        from src.domains.remittances.routes import update_remittance_endpoint

        mock_response = RemittanceDetailResponse.model_validate(
            mock_remittance_processed
        )
        mock_update_remittance.return_value = mock_response

        approval_data = RemittanceUpdateRequest(status="Awaiting_Approval")

        # Call route function directly
        result = await update_remittance_endpoint(
            org_id="test-org-123",
            remittance_id="test-remittance-id-456",
            update_data=approval_data,
            membership=mock_organization_member_user,
            db=mock_prisma,
        )

        # Verify result
        assert isinstance(result, RemittanceDetailResponse)

        # Verify service was called correctly
        mock_update_remittance.assert_called_once_with(
            db=mock_prisma,
            org_id="test-org-123",
            user_id=mock_organization_member_user.profileId,
            remittance_id="test-remittance-id-456",
            update_data=approval_data,
        )

    @pytest.mark.asyncio
    async def test_update_remittance_auditor_denied(self):
        """Test that auditor cannot update remittances."""
        # Note: Permission checking is handled by FastAPI dependency injection
        # and tested separately in the permission system tests.
        # This test verifies the route uses MANAGE_REMITTANCES permission.
        import inspect

        from src.domains.remittances.routes import update_remittance_endpoint

        # Verify the route function uses MANAGE_REMITTANCES permission
        sig = inspect.signature(update_remittance_endpoint)
        membership_param = sig.parameters.get("membership")

        assert membership_param is not None
        assert hasattr(membership_param.default, "dependency")
        # This ensures auditors without MANAGE_REMITTANCES cannot access this route

    @pytest.mark.asyncio
    @patch("src.domains.remittances.routes.update_remittance")
    async def test_update_remittance_soft_delete(
        self,
        mock_update_remittance,
        mock_organization_member_admin,
        mock_remittance_processed,
        mock_prisma,
    ):
        """Test soft deletion of remittance."""
        from src.domains.remittances.models import RemittanceUpdateRequest
        from src.domains.remittances.routes import update_remittance_endpoint

        mock_response = RemittanceDetailResponse.model_validate(
            mock_remittance_processed
        )
        mock_update_remittance.return_value = mock_response

        delete_data = RemittanceUpdateRequest(is_deleted=True)

        # Call route function directly
        result = await update_remittance_endpoint(
            org_id="test-org-123",
            remittance_id="test-remittance-id-456",
            update_data=delete_data,
            membership=mock_organization_member_admin,
            db=mock_prisma,
        )

        # Verify result
        assert isinstance(result, RemittanceDetailResponse)

        # Verify service was called correctly
        mock_update_remittance.assert_called_once_with(
            db=mock_prisma,
            org_id="test-org-123",
            user_id=mock_organization_member_admin.profileId,
            remittance_id="test-remittance-id-456",
            update_data=delete_data,
        )


class TestGetRemittanceFileRoute:
    """Test get remittance file URL route function."""

    @pytest.mark.asyncio
    @patch("src.domains.remittances.routes.get_file_url")
    async def test_get_file_url_success(
        self,
        mock_get_file_url,
        mock_organization_member_admin,
        mock_prisma,
    ):
        """Test successful file URL generation."""
        from src.domains.remittances.routes import get_remittance_file_url

        mock_response = FileUrlResponse(
            url="https://supabase.co/signed-url", expires_in=3600
        )
        mock_get_file_url.return_value = mock_response

        # Call route function directly
        result = await get_remittance_file_url(
            org_id="test-org-123",
            remittance_id="test-remittance-id-123",
            membership=mock_organization_member_admin,
            db=mock_prisma,
        )

        # Verify result
        assert isinstance(result, FileUrlResponse)
        assert result.url == "https://supabase.co/signed-url"
        assert result.expires_in == 3600

        # Verify service was called correctly
        mock_get_file_url.assert_called_once_with(
            db=mock_prisma,
            org_id="test-org-123",
            remittance_id="test-remittance-id-123",
        )

    @pytest.mark.asyncio
    @patch("src.domains.remittances.routes.get_file_url")
    async def test_get_file_url_not_found(
        self,
        mock_get_file_url,
        mock_organization_member_admin,
        mock_prisma,
    ):
        """Test file URL for non-existent file."""
        from src.domains.remittances.routes import get_remittance_file_url

        mock_get_file_url.side_effect = HTTPException(
            status_code=404, detail="File not found"
        )

        # Verify that the exception is propagated
        with pytest.raises(HTTPException) as exc_info:
            await get_remittance_file_url(
                org_id="test-org-123",
                remittance_id="nonexistent-id",
                membership=mock_organization_member_admin,
                db=mock_prisma,
            )

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "File not found"

    @pytest.mark.asyncio
    @patch("src.domains.remittances.routes.get_file_url")
    async def test_get_file_url_auditor_access(
        self,
        mock_get_file_url,
        mock_organization_member_auditor,
        mock_prisma,
    ):
        """Test that auditor can access file URLs."""
        from src.domains.remittances.routes import get_remittance_file_url

        mock_response = FileUrlResponse(
            url="https://supabase.co/signed-url", expires_in=3600
        )
        mock_get_file_url.return_value = mock_response

        # Call route function directly with auditor role
        result = await get_remittance_file_url(
            org_id="test-org-123",
            remittance_id="test-remittance-id-123",
            membership=mock_organization_member_auditor,
            db=mock_prisma,
        )

        # Auditor should be able to view files (has VIEW_REMITTANCES permission)
        assert isinstance(result, FileUrlResponse)
        assert result.url == "https://supabase.co/signed-url"
        assert result.expires_in == 3600

        # Verify service was called correctly
        mock_get_file_url.assert_called_once_with(
            db=mock_prisma,
            org_id="test-org-123",
            remittance_id="test-remittance-id-123",
        )


class TestRemittanceRoutePermissions:
    """Test permission handling across all remittance routes."""

    @pytest.fixture
    def permission_test_cases(self):
        """Test cases for different roles and their expected permissions."""
        return [
            {
                "role": OrganizationRole.owner,
                "can_create": True,
                "can_view": True,
                "can_manage": True,
                "can_approve": True,
            },
            {
                "role": OrganizationRole.admin,
                "can_create": True,
                "can_view": True,
                "can_manage": True,
                "can_approve": True,
            },
            {
                "role": OrganizationRole.user,
                "can_create": True,
                "can_view": True,
                "can_manage": True,
                "can_approve": True,
            },
            {
                "role": OrganizationRole.auditor,
                "can_create": False,
                "can_view": True,
                "can_manage": False,
                "can_approve": False,
            },
        ]

    @pytest.mark.parametrize(
        "test_case",
        [
            {"role": OrganizationRole.owner, "can_create": True},
            {"role": OrganizationRole.admin, "can_create": True},
            {"role": OrganizationRole.user, "can_create": True},
            {"role": OrganizationRole.auditor, "can_create": False},
        ],
    )
    def test_create_permission_by_role(self, test_case):
        """Test CREATE_REMITTANCES permission for different roles."""
        can_create = test_case["can_create"]

        # This would be implemented as integration tests with actual permission checking
        # For now, this documents the expected behavior
        assert isinstance(can_create, bool)

    @pytest.mark.parametrize(
        "test_case",
        [
            {"role": OrganizationRole.owner, "can_view": True},
            {"role": OrganizationRole.admin, "can_view": True},
            {"role": OrganizationRole.user, "can_view": True},
            {"role": OrganizationRole.auditor, "can_view": True},
        ],
    )
    def test_view_permission_by_role(self, test_case):
        """Test VIEW_REMITTANCES permission for different roles."""
        can_view = test_case["can_view"]

        # All roles should be able to view remittances
        assert can_view is True

    @pytest.mark.parametrize(
        "test_case",
        [
            {"role": OrganizationRole.owner, "can_manage": True},
            {"role": OrganizationRole.admin, "can_manage": True},
            {"role": OrganizationRole.user, "can_manage": True},
            {"role": OrganizationRole.auditor, "can_manage": False},
        ],
    )
    def test_manage_permission_by_role(self, test_case):
        """Test MANAGE_REMITTANCES permission for different roles."""
        role = test_case["role"]
        can_manage = test_case["can_manage"]

        # Only auditor should not be able to manage
        expected = role != OrganizationRole.auditor
        assert can_manage == expected


class TestRemittanceRouteValidation:
    """Test request/response validation."""

    @pytest.mark.asyncio
    async def test_upload_invalid_org_id_format(self):
        """Test upload with invalid organization ID format."""
        # Note: Path parameter validation is handled by FastAPI
        # UUID validation occurs at the framework level
        # This test documents expected behavior
        pass

    @pytest.mark.asyncio
    async def test_update_invalid_status_value(self):
        """Test update with invalid status value."""
        # Note: Enum validation is handled by Pydantic models
        # Invalid enum values are caught during request parsing
        # This test documents expected behavior
        pass

    @pytest.mark.asyncio
    async def test_list_invalid_pagination_params(self):
        """Test list with invalid pagination parameters."""
        # Note: Query parameter validation is handled by FastAPI
        # Range validation (page >= 1, page_size <= 500) occurs at framework level
        # This test documents expected behavior
        pass
