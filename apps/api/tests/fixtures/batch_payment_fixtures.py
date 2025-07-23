"""
Test fixtures for batch payment functionality.
"""

from datetime import date
from decimal import Decimal
from typing import Dict, List
from unittest.mock import Mock

import pytest

from src.domains.external_accounting.base.types import BatchPaymentData, PaymentItem


@pytest.fixture
def mock_batch_payment_data() -> BatchPaymentData:
    """Mock BatchPaymentData for testing."""
    return BatchPaymentData(
        account_id="test-account-123",
        payment_date="2024-01-15",
        payment_reference="RM: Batch Payment REF-12345",
        payments=[
            PaymentItem(
                invoice_id="test-invoice-1",
                amount=Decimal("150.00"),
                reference="RM: Payment for Invoice INV-001",
            ),
            PaymentItem(
                invoice_id="test-invoice-2",
                amount=Decimal("250.50"),
                reference="RM: Payment for Invoice INV-002",
            ),
        ],
    )


@pytest.fixture
def mock_xero_batch_payment_response() -> Dict[str, List[Dict[str, str]]]:
    """Mock Xero API batch payment response."""
    return {
        "BatchPayments": [
            {
                "BatchPaymentID": "test-batch-payment-123",
                "Account": {"AccountID": "test-account-123"},
                "Date": "2024-01-15",
                "Reference": "RM: Batch Payment REF-12345",
                "Status": "AUTHORISED",
                "TotalAmount": "400.50",
                "UpdatedDateUTC": "2024-01-15T10:30:00Z",
            }
        ]
    }


@pytest.fixture
def mock_xero_batch_payment_error_response() -> Dict[str, List[Dict[str, str]]]:
    """Mock Xero API error response."""
    return {
        "Type": "ValidationException",
        "Title": "Validation errors",
        "Detail": "The request contains validation errors",
        "ValidationErrors": [
            {"Message": "Invoice not found", "Source": "Payments[0].Invoice.InvoiceID"}
        ],
    }


@pytest.fixture
def mock_remittance_ready_for_approval() -> Mock:
    """Mock Remittance object ready for approval with matched lines."""
    from prisma.enums import RemittanceStatus
    from prisma.models import Remittance

    remittance = Mock(spec=Remittance)
    remittance.id = "test-remittance-approval-123"
    remittance.organizationId = "test-org-123"
    remittance.organization_id = "test-org-123"
    remittance.filename = "approval_remittance.pdf"
    remittance.status = RemittanceStatus.Awaiting_Approval
    remittance.paymentDate = date(2024, 1, 15)
    remittance.payment_date = date(2024, 1, 15)
    remittance.totalAmount = Decimal("400.50")
    remittance.total_amount = Decimal("400.50")
    remittance.reference = "REF-12345"
    remittance.xeroBatchId = None
    remittance.xero_batch_id = None

    # Mock matched remittance lines
    from datetime import datetime

    line1 = Mock()
    line1.id = "line-1"
    line1.invoiceNumber = "INV-001"
    line1.invoice_number = "INV-001"  # For Pydantic model
    line1.aiPaidAmount = Decimal("150.00")
    line1.ai_paid_amount = Decimal("150.00")  # For Pydantic model
    line1.manualPaidAmount = None
    line1.manual_paid_amount = None  # For Pydantic model
    line1.aiInvoiceId = "test-invoice-1"
    line1.ai_invoice_id = "test-invoice-1"  # For Pydantic model
    line1.overrideInvoiceId = None
    line1.override_invoice_id = None  # For Pydantic model
    line1.matchConfidence = None
    line1.match_confidence = None  # For Pydantic model
    line1.matchType = None
    line1.match_type = None  # For Pydantic model
    line1.notes = None
    line1.createdAt = datetime(2024, 1, 15, 9, 0, 0)
    line1.created_at = datetime(2024, 1, 15, 9, 0, 0)  # For Pydantic model
    line1.updatedAt = datetime(2024, 1, 15, 9, 0, 0)
    line1.updated_at = datetime(2024, 1, 15, 9, 0, 0)  # For Pydantic model

    line2 = Mock()
    line2.id = "line-2"
    line2.invoiceNumber = "INV-002"
    line2.invoice_number = "INV-002"  # For Pydantic model
    line2.aiPaidAmount = Decimal("250.50")
    line2.ai_paid_amount = Decimal("250.50")  # For Pydantic model
    line2.manualPaidAmount = None
    line2.manual_paid_amount = None  # For Pydantic model
    line2.aiInvoiceId = "test-invoice-2"
    line2.ai_invoice_id = "test-invoice-2"  # For Pydantic model
    line2.overrideInvoiceId = None
    line2.override_invoice_id = None  # For Pydantic model
    line2.matchConfidence = None
    line2.match_confidence = None  # For Pydantic model
    line2.matchType = None
    line2.match_type = None  # For Pydantic model
    line2.notes = None
    line2.createdAt = datetime(2024, 1, 15, 9, 0, 0)
    line2.created_at = datetime(2024, 1, 15, 9, 0, 0)  # For Pydantic model
    line2.updatedAt = datetime(2024, 1, 15, 9, 0, 0)
    line2.updated_at = datetime(2024, 1, 15, 9, 0, 0)  # For Pydantic model

    remittance.lines = [line1, line2]
    return remittance


@pytest.fixture
def mock_remittance_no_matches() -> Mock:
    """Mock Remittance object with no matched lines."""
    from datetime import datetime

    from prisma.enums import RemittanceStatus
    from prisma.models import Remittance

    remittance = Mock(spec=Remittance)
    remittance.id = "test-remittance-no-matches-456"
    remittance.organizationId = "test-org-123"
    remittance.status = RemittanceStatus.Awaiting_Approval
    remittance.lines = []  # No matched lines
    remittance.createdAt = datetime(2024, 1, 15, 9, 0, 0)
    remittance.updatedAt = datetime(2024, 1, 15, 9, 0, 0)
    return remittance


@pytest.fixture
def mock_bank_account() -> Mock:
    """Mock default bank account for organization."""
    from prisma.models import BankAccount

    account = Mock(spec=BankAccount)
    account.id = "test-bank-account-123"
    account.organizationId = "test-org-123"
    account.xeroAccountId = "test-account-123"
    account.xeroName = "Business Transaction Account"
    account.isDefault = True
    account.currencyCode = "AUD"
    return account


@pytest.fixture
def mock_matched_invoices() -> List[Mock]:
    """Mock invoices that match remittance lines."""
    from prisma.models import Invoice

    invoice1 = Mock(spec=Invoice)
    invoice1.id = "test-invoice-1"
    invoice1.invoiceId = "xero-invoice-1"
    invoice1.invoiceNumber = "INV-001"
    invoice1.total = Decimal("150.00")

    invoice2 = Mock(spec=Invoice)
    invoice2.id = "test-invoice-2"
    invoice2.invoiceId = "xero-invoice-2"
    invoice2.invoiceNumber = "INV-002"
    invoice2.total = Decimal("250.50")

    return [invoice1, invoice2]
