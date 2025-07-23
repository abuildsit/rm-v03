"""
Tests for remittance service functions in src/domains/remittances/service.py

Tests file upload, validation, CRUD operations, and business logic.
"""

from decimal import Decimal
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import HTTPException
from prisma.enums import RemittanceStatus
from prisma.errors import PrismaError

from src.domains.remittances.models import (
    FileUrlResponse,
    RemittanceDetailResponse,
    RemittanceListResponse,
    RemittanceResponse,
    RemittanceUpdateRequest,
)
from src.domains.remittances.service import (
    create_remittance,
    generate_file_path,
    get_file_url,
    get_remittance_by_id,
    get_remittances_by_organization,
    update_remittance,
    upload_file_to_storage_with_content,
    validate_file,
)


class TestRemittanceValidation:
    """Test file validation functions."""

    @pytest.mark.asyncio
    async def test_validate_file_success_pdf(self, mock_pdf_file):
        """Test successful validation of PDF file."""
        # Should not raise an exception
        await validate_file(mock_pdf_file)

    @pytest.mark.asyncio
    async def test_validate_file_invalid_type(self, mock_invalid_file):
        """Test validation failure for invalid file type."""
        with pytest.raises(HTTPException) as exc_info:
            await validate_file(mock_invalid_file)

        assert exc_info.value.status_code == 400
        assert "Only PDF files are allowed" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_validate_file_too_large(self, mock_large_file):
        """Test validation failure for file too large."""
        with pytest.raises(HTTPException) as exc_info:
            await validate_file(mock_large_file)

        assert exc_info.value.status_code == 400
        assert "File size exceeds maximum limit" in str(exc_info.value.detail)


class TestFilePathGeneration:
    """Test file path generation."""

    @patch("src.domains.remittances.service.datetime")
    @patch("src.domains.remittances.service.uuid")
    def test_generate_file_path(self, mock_uuid, mock_datetime):
        """Test file path generation with mocked date and UUID."""
        # Mock datetime
        mock_now = Mock()
        mock_now.year = 2024
        mock_now.month = 3
        mock_datetime.now.return_value = mock_now

        # Mock UUID
        mock_uuid.uuid4.return_value = Mock()
        mock_uuid.uuid4.return_value.__str__ = Mock(return_value="test-uuid-123")

        org_id = "test-org-123"
        file_path, unique_id = generate_file_path(org_id)

        assert file_path == "test-org-123/2024/03/test-uuid-123"
        assert unique_id == "test-uuid-123"
        mock_datetime.now.assert_called_once()
        mock_uuid.uuid4.assert_called_once()


class TestFileUpload:
    """Test file upload to Supabase Storage."""

    @pytest.mark.asyncio
    @patch("src.domains.remittances.service.supabase")
    async def test_upload_file_to_storage_with_content_success(
        self, mock_supabase, mock_pdf_file
    ):
        """Test successful file upload to storage."""
        # Mock Supabase response
        mock_response = Mock()
        mock_response.error = None
        mock_supabase.storage.from_.return_value.upload.return_value = mock_response

        file_path = "test-org/2024/01/test-uuid"
        result = await upload_file_to_storage_with_content(
            b"pdf content", file_path, "application/pdf"
        )

        assert result == file_path
        mock_supabase.storage.from_.assert_called_with("remittances")

    @pytest.mark.asyncio
    @patch("src.domains.remittances.service.supabase")
    async def test_upload_file_to_storage_with_content_error(
        self, mock_supabase, mock_pdf_file
    ):
        """Test file upload error handling."""
        # Mock Supabase error
        mock_response = Mock()
        mock_response.error = Mock()
        mock_response.error.message = "Storage error"
        mock_supabase.storage.from_.return_value.upload.return_value = mock_response

        with pytest.raises(HTTPException) as exc_info:
            await upload_file_to_storage_with_content(
                b"pdf content", "test-path", "application/pdf"
            )

        assert exc_info.value.status_code == 500
        assert "Failed to upload file" in str(exc_info.value.detail)


class TestCreateRemittance:
    """Test remittance creation."""

    @pytest.mark.asyncio
    @patch("src.domains.remittances.service.upload_file_to_storage_with_content")
    @patch("src.domains.remittances.service.generate_file_path")
    async def test_create_remittance_success(
        self,
        mock_generate_path,
        mock_upload,
        mock_prisma,
        mock_pdf_file,
        mock_remittance_uploaded,
    ):
        """Test successful remittance creation."""
        # Mock path generation
        mock_generate_path.return_value = ("test-path", "test-uuid")

        # Mock file upload
        mock_upload.return_value = "test-path"

        # Mock database operations
        mock_prisma.remittance.create = AsyncMock(return_value=mock_remittance_uploaded)
        mock_prisma.auditlog.create = AsyncMock()

        # Mock background tasks
        from fastapi import BackgroundTasks

        background_tasks = BackgroundTasks()

        result = await create_remittance(
            mock_prisma,
            "test-org-123",
            "test-user-123",
            mock_pdf_file,
            background_tasks,
        )

        assert isinstance(result, RemittanceResponse)
        assert result.id == "test-remittance-id-123"
        assert result.filename == "test_remittance.pdf"

        mock_prisma.remittance.create.assert_called_once()
        mock_prisma.auditlog.create.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.domains.remittances.service.upload_file_to_storage_with_content")
    @patch("src.domains.remittances.service.generate_file_path")
    @patch("src.domains.remittances.service.supabase")
    async def test_create_remittance_db_error_cleanup(
        self, mock_supabase, mock_generate_path, mock_upload, mock_prisma, mock_pdf_file
    ):
        """Test database error with file cleanup."""
        # Mock path generation and upload
        mock_generate_path.return_value = ("test-path", "test-uuid")
        mock_upload.return_value = "test-path"

        # Mock database error
        mock_prisma.remittance.create = AsyncMock(side_effect=PrismaError("DB error"))

        # Mock supabase cleanup
        mock_supabase.storage.from_.return_value.remove.return_value = None

        # Mock background tasks
        from fastapi import BackgroundTasks

        background_tasks = BackgroundTasks()

        with pytest.raises(HTTPException) as exc_info:
            await create_remittance(
                mock_prisma,
                "test-org-123",
                "test-user-123",
                mock_pdf_file,
                background_tasks,
            )

        assert exc_info.value.status_code == 500
        assert "Failed to create remittance record" in str(exc_info.value.detail)

        # Verify cleanup was attempted
        mock_supabase.storage.from_.assert_called_with("remittances")


class TestGetRemittancesList:
    """Test getting remittances list with pagination and filtering."""

    @pytest.mark.asyncio
    async def test_get_remittances_basic_success(
        self, mock_prisma, mock_remittance_uploaded
    ):
        """Test basic remittances list retrieval."""
        mock_prisma.remittance.count = AsyncMock(return_value=1)
        mock_prisma.remittance.find_many = AsyncMock(
            return_value=[mock_remittance_uploaded]
        )

        result = await get_remittances_by_organization(mock_prisma, "test-org-123")

        assert isinstance(result, RemittanceListResponse)
        assert result.total == 1
        assert result.page == 1
        assert result.page_size == 50
        assert len(result.remittances) == 1

    @pytest.mark.asyncio
    async def test_get_remittances_with_status_filter(
        self, mock_prisma, mock_remittance_uploaded
    ):
        """Test remittances list with status filter."""
        mock_prisma.remittance.count = AsyncMock(return_value=1)
        mock_prisma.remittance.find_many = AsyncMock(
            return_value=[mock_remittance_uploaded]
        )

        result = await get_remittances_by_organization(
            mock_prisma, "test-org-123", status_filter="Uploaded"
        )

        assert result.total == 1
        # Verify the where clause included status filter
        call_args = mock_prisma.remittance.count.call_args[1]
        assert "where" in call_args

    @pytest.mark.asyncio
    async def test_get_remittances_invalid_status_filter(self, mock_prisma):
        """Test remittances list with invalid status filter."""
        with pytest.raises(HTTPException) as exc_info:
            await get_remittances_by_organization(
                mock_prisma, "test-org-123", status_filter="InvalidStatus"
            )

        assert exc_info.value.status_code == 400
        assert "Invalid status filter" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_get_remittances_with_date_filters(
        self, mock_prisma, mock_remittance_uploaded
    ):
        """Test remittances list with date range filters."""
        mock_prisma.remittance.count = AsyncMock(return_value=1)
        mock_prisma.remittance.find_many = AsyncMock(
            return_value=[mock_remittance_uploaded]
        )

        result = await get_remittances_by_organization(
            mock_prisma,
            "test-org-123",
            date_from="2024-01-01T00:00:00Z",
            date_to="2024-01-31T23:59:59Z",
        )

        assert result.total == 1

    @pytest.mark.asyncio
    async def test_get_remittances_invalid_date_format(self, mock_prisma):
        """Test remittances list with invalid date format."""
        with pytest.raises(HTTPException) as exc_info:
            await get_remittances_by_organization(
                mock_prisma, "test-org-123", date_from="invalid-date"
            )

        assert exc_info.value.status_code == 400
        assert "Invalid date_from format" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_get_remittances_with_search(
        self, mock_prisma, mock_remittance_uploaded
    ):
        """Test remittances list with search filter."""
        mock_prisma.remittance.count = AsyncMock(return_value=1)
        mock_prisma.remittance.find_many = AsyncMock(
            return_value=[mock_remittance_uploaded]
        )

        result = await get_remittances_by_organization(
            mock_prisma, "test-org-123", search="test"
        )

        assert result.total == 1


class TestGetRemittanceById:
    """Test getting single remittance by ID."""

    @pytest.mark.asyncio
    async def test_get_remittance_success(
        self, mock_prisma, mock_remittance_processed, mock_remittance_line
    ):
        """Test successful remittance retrieval with lines."""
        mock_remittance_processed.lines = [mock_remittance_line]
        mock_prisma.remittance.find_unique = AsyncMock(
            return_value=mock_remittance_processed
        )

        result = await get_remittance_by_id(
            mock_prisma, "test-org-123", "test-remittance-id-456"
        )

        assert isinstance(result, RemittanceDetailResponse)
        assert result.id == "test-remittance-id-456"
        assert len(result.lines) == 1

    @pytest.mark.asyncio
    async def test_get_remittance_not_found(self, mock_prisma):
        """Test remittance not found error."""
        mock_prisma.remittance.find_unique = AsyncMock(return_value=None)

        with pytest.raises(HTTPException) as exc_info:
            await get_remittance_by_id(mock_prisma, "test-org-123", "nonexistent-id")

        assert exc_info.value.status_code == 404
        assert "Remittance not found" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_get_remittance_wrong_organization(
        self, mock_prisma, mock_remittance_processed
    ):
        """Test remittance access from wrong organization."""
        mock_remittance_processed.organizationId = "different-org-id"
        mock_prisma.remittance.find_unique = AsyncMock(
            return_value=mock_remittance_processed
        )

        with pytest.raises(HTTPException) as exc_info:
            await get_remittance_by_id(
                mock_prisma, "test-org-123", "test-remittance-id-456"
            )

        assert exc_info.value.status_code == 404
        assert "Remittance not found" in str(exc_info.value.detail)


class TestUpdateRemittance:
    """Test remittance update operations."""

    @pytest.mark.asyncio
    async def test_update_remittance_success(
        self, mock_prisma, mock_remittance_uploaded, mock_remittance_processed
    ):
        """Test successful remittance update."""
        # Mock existing remittance
        mock_prisma.remittance.find_unique = AsyncMock(
            return_value=mock_remittance_uploaded
        )

        # Mock updated remittance
        mock_prisma.remittance.update = AsyncMock(
            return_value=mock_remittance_processed
        )
        mock_prisma.auditlog.create = AsyncMock()

        update_data = RemittanceUpdateRequest(
            status=RemittanceStatus.Data_Retrieved, total_amount=Decimal("1500.50")
        )

        result = await update_remittance(
            mock_prisma,
            "test-org-123",
            "test-user-123",
            "test-remittance-id-123",
            update_data,
        )

        assert isinstance(result, RemittanceDetailResponse)
        mock_prisma.remittance.update.assert_called_once()
        mock_prisma.auditlog.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_remittance_not_found(self, mock_prisma):
        """Test update of non-existent remittance."""
        mock_prisma.remittance.find_unique = AsyncMock(return_value=None)

        update_data = RemittanceUpdateRequest(status=RemittanceStatus.Data_Retrieved)

        with pytest.raises(HTTPException) as exc_info:
            await update_remittance(
                mock_prisma,
                "test-org-123",
                "test-user-123",
                "nonexistent-id",
                update_data,
            )

        assert exc_info.value.status_code == 404
        assert "Remittance not found" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    @patch("src.domains.remittances.service.get_remittance_by_id")
    async def test_update_remittance_no_changes(
        self, mock_get_remittance, mock_prisma, mock_remittance_uploaded
    ):
        """Test update with no changes returns existing remittance."""
        mock_prisma.remittance.find_unique = AsyncMock(
            return_value=mock_remittance_uploaded
        )
        mock_get_remittance.return_value = mock_remittance_uploaded

        # Empty update data
        update_data = RemittanceUpdateRequest()

        await update_remittance(
            mock_prisma,
            "test-org-123",
            "test-user-123",
            "test-remittance-id-123",
            update_data,
        )

        # Should call get_remittance_by_id instead of update
        mock_get_remittance.assert_called_once()


class TestGetFileUrl:
    """Test getting signed URL for remittance files."""

    @pytest.mark.asyncio
    @patch("src.domains.remittances.service.supabase")
    async def test_get_file_url_success(
        self, mock_supabase, mock_prisma, mock_remittance_uploaded
    ):
        """Test successful signed URL generation."""
        mock_prisma.remittance.find_unique = AsyncMock(
            return_value=mock_remittance_uploaded
        )

        # Mock Supabase response
        mock_supabase.storage.from_.return_value.create_signed_url.return_value = {
            "signedURL": "https://supabase.co/signed-url",
            "error": None,
        }

        result = await get_file_url(
            mock_prisma, "test-org-123", "test-remittance-id-123"
        )

        assert isinstance(result, FileUrlResponse)
        assert result.url == "https://supabase.co/signed-url"
        assert result.expires_in == 3600

    @pytest.mark.asyncio
    async def test_get_file_url_remittance_not_found(self, mock_prisma):
        """Test file URL for non-existent remittance."""
        mock_prisma.remittance.find_unique = AsyncMock(return_value=None)

        with pytest.raises(HTTPException) as exc_info:
            await get_file_url(mock_prisma, "test-org-123", "nonexistent-id")

        assert exc_info.value.status_code == 404
        assert "Remittance not found" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_get_file_url_no_file_path(
        self, mock_prisma, mock_remittance_uploaded
    ):
        """Test file URL when remittance has no file path."""
        mock_remittance_uploaded.filePath = None
        mock_prisma.remittance.find_unique = AsyncMock(
            return_value=mock_remittance_uploaded
        )

        with pytest.raises(HTTPException) as exc_info:
            await get_file_url(mock_prisma, "test-org-123", "test-remittance-id-123")

        assert exc_info.value.status_code == 404
        assert "File not found" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    @patch("src.domains.remittances.service.supabase")
    async def test_get_file_url_supabase_error(
        self, mock_supabase, mock_prisma, mock_remittance_uploaded
    ):
        """Test signed URL generation with Supabase error."""
        mock_prisma.remittance.find_unique = AsyncMock(
            return_value=mock_remittance_uploaded
        )

        # Mock Supabase error
        mock_supabase.storage.from_.return_value.create_signed_url.return_value = {
            "signedURL": None,
            "error": {"message": "Storage error"},
        }

        with pytest.raises(HTTPException) as exc_info:
            await get_file_url(mock_prisma, "test-org-123", "test-remittance-id-123")

        assert exc_info.value.status_code == 500
        assert "Failed to generate file URL" in str(exc_info.value.detail)
