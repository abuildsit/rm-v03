"""
Tests for remittance models in src/domains/remittances/models.py

Tests Pydantic model validation, serialization, and edge cases.
"""

from datetime import datetime
from decimal import Decimal

import pytest
from prisma.enums import RemittanceStatus
from pydantic import ValidationError

from src.domains.remittances.models import (
    FileUploadResponse,
    FileUrlResponse,
    RemittanceDetailResponse,
    RemittanceLineResponse,
    RemittanceListResponse,
    RemittanceResponse,
    RemittanceUpdateRequest,
)


class TestRemittanceLineResponse:
    """Test RemittanceLineResponse model."""

    def test_remittance_line_response_valid(self):
        """Test valid RemittanceLineResponse creation."""
        data = {
            "id": "line-123",
            "invoice_number": "INV-001",
            "ai_paid_amount": Decimal("500.00"),
            "manual_paid_amount": Decimal("500.00"),
            "ai_invoice_id": "invoice-123",
            "override_invoice_id": "invoice-456",
            "created_at": datetime(2024, 1, 15, 9, 0, 0),
            "updated_at": datetime(2024, 1, 15, 9, 0, 0),
        }

        line = RemittanceLineResponse(**data)

        assert line.id == "line-123"
        assert line.invoice_number == "INV-001"
        assert line.ai_paid_amount == Decimal("500.00")
        assert line.manual_paid_amount == Decimal("500.00")

    def test_remittance_line_response_minimal(self):
        """Test RemittanceLineResponse with minimal required fields."""
        data = {
            "id": "line-123",
            "invoice_number": "INV-001",
        }

        line = RemittanceLineResponse(**data)

        assert line.id == "line-123"
        assert line.invoice_number == "INV-001"
        assert line.ai_paid_amount is None
        assert line.manual_paid_amount is None

    def test_remittance_line_response_serialization(self):
        """Test RemittanceLineResponse JSON serialization."""
        data = {
            "id": "line-123",
            "invoice_number": "INV-001",
            "ai_paid_amount": Decimal("500.00"),
        }

        line = RemittanceLineResponse(**data)
        serialized = line.model_dump()

        assert serialized["id"] == "line-123"
        assert serialized["invoice_number"] == "INV-001"
        assert serialized["ai_paid_amount"] == Decimal("500.00")


class TestRemittanceResponse:
    """Test RemittanceResponse model."""

    def test_remittance_response_valid(self):
        """Test valid RemittanceResponse creation."""
        data = {
            "id": "remittance-123",
            "organization_id": "org-123",
            "filename": "test.pdf",
            "file_path": "org-123/2024/01/uuid",
            "status": RemittanceStatus.Uploaded,
            "payment_date": datetime(2024, 1, 10).date(),
            "total_amount": Decimal("1500.50"),
            "reference": "REF-12345",
            "confidence_score": Decimal("0.95"),
            "xero_batch_id": "batch-123",
            "created_at": datetime(2024, 1, 15, 9, 0, 0),
            "updated_at": datetime(2024, 1, 15, 9, 0, 0),
        }

        remittance = RemittanceResponse(**data)

        assert remittance.id == "remittance-123"
        assert remittance.organization_id == "org-123"
        assert remittance.status == RemittanceStatus.Uploaded
        assert remittance.total_amount == Decimal("1500.50")

    def test_remittance_response_minimal(self):
        """Test RemittanceResponse with minimal required fields."""
        data = {
            "id": "remittance-123",
            "organization_id": "org-123",
            "filename": "test.pdf",
            "status": RemittanceStatus.Uploaded,
        }

        remittance = RemittanceResponse(**data)

        assert remittance.id == "remittance-123"
        assert remittance.file_path is None
        assert remittance.total_amount is None

    def test_remittance_response_all_statuses(self):
        """Test RemittanceResponse with all possible status values."""
        base_data = {
            "id": "remittance-123",
            "organization_id": "org-123",
            "filename": "test.pdf",
        }

        for status in RemittanceStatus:
            data = {**base_data, "status": status}
            remittance = RemittanceResponse(**data)
            assert remittance.status == status


class TestRemittanceDetailResponse:
    """Test RemittanceDetailResponse model."""

    def test_remittance_detail_response_with_lines(self):
        """Test RemittanceDetailResponse with remittance lines."""
        line_data = {
            "id": "line-123",
            "invoice_number": "INV-001",
            "ai_paid_amount": Decimal("500.00"),
        }

        data = {
            "id": "remittance-123",
            "organization_id": "org-123",
            "filename": "test.pdf",
            "status": RemittanceStatus.Data_Retrieved,
            "lines": [line_data],
        }

        remittance = RemittanceDetailResponse(**data)

        assert len(remittance.lines) == 1
        assert isinstance(remittance.lines[0], RemittanceLineResponse)
        assert remittance.lines[0].id == "line-123"

    def test_remittance_detail_response_empty_lines(self):
        """Test RemittanceDetailResponse with empty lines."""
        data = {
            "id": "remittance-123",
            "organization_id": "org-123",
            "filename": "test.pdf",
            "status": RemittanceStatus.Uploaded,
        }

        remittance = RemittanceDetailResponse(**data)

        assert remittance.lines == []


class TestRemittanceListResponse:
    """Test RemittanceListResponse model."""

    def test_remittance_list_response_valid(self):
        """Test valid RemittanceListResponse creation."""
        remittance_data = {
            "id": "remittance-123",
            "organization_id": "org-123",
            "filename": "test.pdf",
            "status": RemittanceStatus.Uploaded,
        }

        data = {
            "remittances": [remittance_data],
            "total": 1,
            "page": 1,
            "page_size": 50,
            "total_pages": 1,
        }

        response = RemittanceListResponse(**data)

        assert len(response.remittances) == 1
        assert response.total == 1
        assert response.page == 1
        assert response.total_pages == 1

    def test_remittance_list_response_empty(self):
        """Test RemittanceListResponse with empty list."""
        data = {
            "remittances": [],
            "total": 0,
            "page": 1,
            "page_size": 50,
            "total_pages": 0,
        }

        response = RemittanceListResponse(**data)

        assert response.remittances == []
        assert response.total == 0

    def test_remittance_list_response_pagination_math(self):
        """Test RemittanceListResponse with various pagination scenarios."""
        test_cases = [
            {"total": 0, "page_size": 50, "expected_pages": 0},
            {"total": 1, "page_size": 50, "expected_pages": 1},
            {"total": 50, "page_size": 50, "expected_pages": 1},
            {"total": 51, "page_size": 50, "expected_pages": 2},
            {"total": 100, "page_size": 25, "expected_pages": 4},
        ]

        for case in test_cases:
            data = {
                "remittances": [],
                "total": case["total"],
                "page": 1,
                "page_size": case["page_size"],
                "total_pages": case["expected_pages"],
            }

            response = RemittanceListResponse(**data)
            assert response.total_pages == case["expected_pages"]


class TestRemittanceUpdateRequest:
    """Test RemittanceUpdateRequest model."""

    def test_remittance_update_request_valid(self):
        """Test valid RemittanceUpdateRequest creation."""
        data = {
            "status": RemittanceStatus.Data_Retrieved,
            "payment_date": datetime(2024, 1, 10).date(),
            "total_amount": Decimal("1500.50"),
            "reference": "REF-12345",
            "is_deleted": False,
        }

        request = RemittanceUpdateRequest(**data)

        assert request.status == RemittanceStatus.Data_Retrieved
        assert request.total_amount == Decimal("1500.50")
        assert request.reference == "REF-12345"
        assert request.is_deleted is False

    def test_remittance_update_request_empty(self):
        """Test RemittanceUpdateRequest with no fields."""
        request = RemittanceUpdateRequest()

        assert request.status is None
        assert request.payment_date is None
        assert request.total_amount is None
        assert request.reference is None
        assert request.is_deleted is None

    def test_remittance_update_request_soft_delete(self):
        """Test RemittanceUpdateRequest for soft deletion."""
        data = {"is_deleted": True}

        request = RemittanceUpdateRequest(**data)

        assert request.is_deleted is True

    def test_remittance_update_request_status_only(self):
        """Test RemittanceUpdateRequest with status change only."""
        data = {"status": RemittanceStatus.Awaiting_Approval}

        request = RemittanceUpdateRequest(**data)

        assert request.status == RemittanceStatus.Awaiting_Approval
        assert request.total_amount is None

    def test_remittance_update_request_invalid_amount(self):
        """Test RemittanceUpdateRequest with invalid amount format."""
        # This would test Decimal validation if more strict validation was added
        data = {"total_amount": "invalid"}

        with pytest.raises(ValidationError):
            RemittanceUpdateRequest(**data)


class TestFileUploadResponse:
    """Test FileUploadResponse model."""

    def test_file_upload_response_valid(self):
        """Test valid FileUploadResponse creation."""
        data = {
            "message": "File uploaded successfully",
            "remittance_id": "remittance-123",
            "filename": "test.pdf",
            "file_path": "org-123/2024/01/uuid",
        }

        response = FileUploadResponse(**data)

        assert response.message == "File uploaded successfully"
        assert response.remittance_id == "remittance-123"
        assert response.filename == "test.pdf"
        assert response.file_path == "org-123/2024/01/uuid"

    def test_file_upload_response_required_fields(self):
        """Test FileUploadResponse with missing required fields."""
        with pytest.raises(ValidationError):
            FileUploadResponse()

    def test_file_upload_response_serialization(self):
        """Test FileUploadResponse JSON serialization."""
        data = {
            "message": "File uploaded successfully",
            "remittance_id": "remittance-123",
            "filename": "test.pdf",
            "file_path": "org-123/2024/01/uuid",
        }

        response = FileUploadResponse(**data)
        serialized = response.model_dump()

        assert serialized == data


class TestFileUrlResponse:
    """Test FileUrlResponse model."""

    def test_file_url_response_valid(self):
        """Test valid FileUrlResponse creation."""
        data = {
            "url": "https://supabase.co/signed-url",
            "expires_in": 3600,
        }

        response = FileUrlResponse(**data)

        assert response.url == "https://supabase.co/signed-url"
        assert response.expires_in == 3600

    def test_file_url_response_default_expiry(self):
        """Test FileUrlResponse with default expiry."""
        data = {"url": "https://supabase.co/signed-url"}

        response = FileUrlResponse(**data)

        assert response.expires_in == 3600  # Default value

    def test_file_url_response_custom_expiry(self):
        """Test FileUrlResponse with custom expiry."""
        data = {
            "url": "https://supabase.co/signed-url",
            "expires_in": 1800,
        }

        response = FileUrlResponse(**data)

        assert response.expires_in == 1800

    def test_file_url_response_required_url(self):
        """Test FileUrlResponse with missing URL."""
        with pytest.raises(ValidationError):
            FileUrlResponse(expires_in=3600)


class TestModelEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_decimal_precision_handling(self):
        """Test Decimal field precision handling."""
        # Test high precision amounts
        data = {
            "id": "remittance-123",
            "organization_id": "org-123",
            "filename": "test.pdf",
            "status": RemittanceStatus.Uploaded,
            "total_amount": Decimal("999999999999999.99"),  # Max precision
        }

        remittance = RemittanceResponse(**data)
        assert remittance.total_amount == Decimal("999999999999999.99")

    def test_confidence_score_range(self):
        """Test confidence score decimal range."""
        # Test various confidence scores
        confidence_scores = [
            Decimal("0.00"),
            Decimal("0.50"),
            Decimal("0.95"),
            Decimal("1.00"),
        ]

        for score in confidence_scores:
            data = {
                "id": "remittance-123",
                "organization_id": "org-123",
                "filename": "test.pdf",
                "status": RemittanceStatus.Data_Retrieved,
                "confidence_score": score,
            }

            remittance = RemittanceResponse(**data)
            assert remittance.confidence_score == score

    def test_long_filename_handling(self):
        """Test handling of long filenames."""
        long_filename = "a" * 255 + ".pdf"

        data = {
            "id": "remittance-123",
            "organization_id": "org-123",
            "filename": long_filename,
            "status": RemittanceStatus.Uploaded,
        }

        remittance = RemittanceResponse(**data)
        assert remittance.filename == long_filename

    def test_special_characters_in_reference(self):
        """Test handling of special characters in reference."""
        special_refs = [
            "REF-12345",
            "PAYMENT/2024/001",
            "TXN_ABC_123",
            "WIRE-789456 (URGENT)",
            "Reference with spaces",
        ]

        for ref in special_refs:
            data = {
                "id": "remittance-123",
                "organization_id": "org-123",
                "filename": "test.pdf",
                "status": RemittanceStatus.Data_Retrieved,
                "reference": ref,
            }

            remittance = RemittanceResponse(**data)
            assert remittance.reference == ref

    def test_datetime_timezone_handling(self):
        """Test datetime field timezone handling."""
        # Test various datetime formats
        test_dates = [
            datetime(2024, 1, 15, 9, 0, 0),  # Naive datetime
            datetime(2024, 1, 15, 9, 0, 0).replace(
                microsecond=123456
            ),  # With microseconds
        ]

        for test_date in test_dates:
            data = {
                "id": "remittance-123",
                "organization_id": "org-123",
                "filename": "test.pdf",
                "status": RemittanceStatus.Uploaded,
                "created_at": test_date,
            }

            remittance = RemittanceResponse(**data)
            assert remittance.created_at == test_date
