"""
Test fixtures and factories for remittance-related test data.
"""

from datetime import datetime
from decimal import Decimal
from io import BytesIO
from typing import Any, Dict, List
from unittest.mock import Mock

import pytest
from fastapi import UploadFile
from prisma.enums import RemittanceStatus
from prisma.models import Remittance, RemittanceLine


@pytest.fixture
def mock_remittance_uploaded() -> Mock:
    """Mock Remittance object with Uploaded status for testing."""
    remittance = Mock(spec=Remittance)
    remittance.id = "test-remittance-id-123"
    remittance.organizationId = "test-org-123"
    remittance.organization_id = "test-org-123"  # For Pydantic model
    remittance.filename = "test_remittance.pdf"
    remittance.filePath = "test-org-123/2024/01/uuid-123"
    remittance.file_path = "test-org-123/2024/01/uuid-123"  # For Pydantic model
    remittance.status = RemittanceStatus.Uploaded
    remittance.paymentDate = None
    remittance.payment_date = None  # For Pydantic model
    remittance.totalAmount = None
    remittance.total_amount = None  # For Pydantic model
    remittance.reference = None
    remittance.confidenceScore = None
    remittance.confidence_score = None  # For Pydantic model
    remittance.extractedRawJson = None
    remittance.xeroBatchId = None
    remittance.xero_batch_id = None  # For Pydantic model
    remittance.createdAt = datetime(2024, 1, 15, 9, 0, 0)
    remittance.created_at = datetime(2024, 1, 15, 9, 0, 0)  # For Pydantic model
    remittance.updatedAt = datetime(2024, 1, 15, 9, 0, 0)
    remittance.updated_at = datetime(2024, 1, 15, 9, 0, 0)  # For Pydantic model
    remittance.lines = []
    return remittance


@pytest.fixture
def mock_remittance_processed() -> Mock:
    """Mock Remittance object with processed data for testing."""
    remittance = Mock(spec=Remittance)
    remittance.id = "test-remittance-id-456"
    remittance.organizationId = "test-org-123"
    remittance.organization_id = "test-org-123"  # For Pydantic model
    remittance.filename = "processed_remittance.pdf"
    remittance.filePath = "test-org-123/2024/01/uuid-456"
    remittance.file_path = "test-org-123/2024/01/uuid-456"  # For Pydantic model
    remittance.status = RemittanceStatus.Data_Retrieved
    remittance.paymentDate = datetime(2024, 1, 10).date()
    remittance.payment_date = datetime(2024, 1, 10).date()  # For Pydantic model
    remittance.totalAmount = Decimal("1500.50")
    remittance.total_amount = Decimal("1500.50")  # For Pydantic model
    remittance.reference = "REF-12345"
    remittance.confidenceScore = Decimal("0.95")
    remittance.confidence_score = Decimal("0.95")  # For Pydantic model
    remittance.extractedRawJson = {"invoices": []}
    remittance.xeroBatchId = None
    remittance.xero_batch_id = None  # For Pydantic model
    remittance.createdAt = datetime(2024, 1, 15, 9, 0, 0)
    remittance.created_at = datetime(2024, 1, 15, 9, 0, 0)  # For Pydantic model
    remittance.updatedAt = datetime(2024, 1, 15, 10, 0, 0)
    remittance.updated_at = datetime(2024, 1, 15, 10, 0, 0)  # For Pydantic model
    remittance.lines = []
    return remittance


@pytest.fixture
def mock_remittance_line() -> Mock:
    """Mock RemittanceLine object for testing."""
    line = Mock(spec=RemittanceLine)
    line.id = "test-line-id-123"
    line.remittanceId = "test-remittance-id-456"
    line.invoiceNumber = "INV-001"
    line.invoice_number = "INV-001"  # For Pydantic model
    line.aiPaidAmount = Decimal("500.00")
    line.ai_paid_amount = Decimal("500.00")  # For Pydantic model
    line.manualPaidAmount = None
    line.manual_paid_amount = None  # For Pydantic model
    line.aiInvoiceId = "test-invoice-id-123"
    line.ai_invoice_id = "test-invoice-id-123"  # For Pydantic model
    line.overrideInvoiceId = None
    line.override_invoice_id = None  # For Pydantic model
    line.createdAt = datetime(2024, 1, 15, 9, 0, 0)
    line.created_at = datetime(2024, 1, 15, 9, 0, 0)  # For Pydantic model
    line.updatedAt = datetime(2024, 1, 15, 9, 0, 0)
    line.updated_at = datetime(2024, 1, 15, 9, 0, 0)  # For Pydantic model
    return line


@pytest.fixture
def mock_pdf_file() -> UploadFile:
    """Mock PDF UploadFile for testing."""
    content = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n"
    file_obj = BytesIO(content)
    return UploadFile(
        filename="test_remittance.pdf",
        file=file_obj,
        size=len(content),
        headers={"content-type": "application/pdf"},
    )


@pytest.fixture
def mock_invalid_file() -> UploadFile:
    """Mock invalid file for testing validation."""
    content = b"This is not a PDF file"
    file_obj = BytesIO(content)
    return UploadFile(
        filename="test_file.txt",
        file=file_obj,
        size=len(content),
        headers={"content-type": "text/plain"},
    )


@pytest.fixture
def mock_large_file() -> UploadFile:
    """Mock large file exceeding size limit for testing."""
    # Create a file larger than 10MB
    content = b"x" * (11 * 1024 * 1024)
    file_obj = BytesIO(content)
    return UploadFile(
        filename="large_file.pdf",
        file=file_obj,
        size=len(content),
        headers={"content-type": "application/pdf"},
    )


@pytest.fixture
def remittance_update_request() -> Dict[str, Any]:
    """Valid remittance update request data."""
    return {
        "status": RemittanceStatus.Awaiting_Approval,
        "payment_date": datetime(2024, 1, 10).date(),
        "total_amount": Decimal("1500.50"),
        "reference": "REF-12345",
    }


@pytest.fixture
def remittance_list_response_data() -> Dict[str, Any]:
    """Mock remittance list response data for testing."""
    return {"remittances": [], "total": 0, "page": 1, "page_size": 50, "total_pages": 0}


class RemittanceTestData:
    """Helper class for generating consistent remittance test data."""

    @staticmethod
    def remittance_ids() -> Dict[str, str]:
        """Standard test remittance IDs."""
        return {
            "uploaded": "test-remittance-id-123",
            "processed": "test-remittance-id-456",
            "approved": "test-remittance-id-789",
        }

    @staticmethod
    def organization_ids() -> Dict[str, str]:
        """Standard test organization IDs."""
        return {
            "default": "test-org-id-123",
            "different": "different-org-id-456",
        }

    @staticmethod
    def file_paths() -> Dict[str, str]:
        """Standard test file paths."""
        return {
            "default": "test-org-id-123/2024/01/uuid-123",
            "processed": "test-org-id-123/2024/01/uuid-456",
        }

    @staticmethod
    def remittance_statuses() -> List[RemittanceStatus]:
        """Available remittance statuses."""
        return [
            RemittanceStatus.Uploaded,
            RemittanceStatus.Processing,
            RemittanceStatus.Data_Retrieved,
            RemittanceStatus.Awaiting_Approval,
            RemittanceStatus.Unmatched,
            RemittanceStatus.Partially_Matched,
            RemittanceStatus.Manual_Review,
            RemittanceStatus.Exporting,
            RemittanceStatus.Exported_Unreconciled,
            RemittanceStatus.Reconciled,
        ]

    @staticmethod
    def valid_filenames() -> List[str]:
        """Valid PDF filenames for testing."""
        return [
            "remittance.pdf",
            "payment_advice_2024.pdf",
            "bank_statement.pdf",
            "invoice_payment.PDF",
        ]

    @staticmethod
    def invalid_filenames() -> List[str]:
        """Invalid filenames for testing."""
        return [
            "document.txt",
            "image.jpg",
            "spreadsheet.xlsx",
            "presentation.pptx",
        ]

    @staticmethod
    def sample_amounts() -> List[Decimal]:
        """Sample payment amounts for testing."""
        return [
            Decimal("100.00"),
            Decimal("1500.50"),
            Decimal("25000.99"),
            Decimal("0.01"),
        ]

    @staticmethod
    def sample_references() -> List[str]:
        """Sample payment references for testing."""
        return [
            "REF-12345",
            "PAYMENT-2024-001",
            "WIRE-789456",
            "TXN-ABC123",
        ]

    @staticmethod
    def pagination_params() -> Dict[str, Dict[str, Any]]:
        """Common pagination parameters for testing."""
        return {
            "default": {"page": 1, "page_size": 50},
            "small": {"page": 1, "page_size": 10},
            "large": {"page": 1, "page_size": 500},
            "second_page": {"page": 2, "page_size": 50},
        }

    @staticmethod
    def filter_params() -> Dict[str, Dict[str, Any]]:
        """Common filter parameters for testing."""
        return {
            "by_status": {"status_filter": "Uploaded"},
            "by_date": {"date_from": "2024-01-01", "date_to": "2024-01-31"},
            "by_search": {"search": "REF-12345"},
            "combined": {
                "status_filter": "Data_Retrieved",
                "date_from": "2024-01-01",
                "search": "payment",
            },
        }
