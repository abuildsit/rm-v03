"""
Test fixtures and factories for invoice-related test data.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from unittest.mock import Mock

import pytest
from prisma.enums import InvoiceStatus
from prisma.models import Invoice


@pytest.fixture
def mock_invoice() -> Mock:
    """Mock Invoice object for testing."""
    invoice = Mock(spec=Invoice)
    invoice.id = "test-invoice-id-123"
    invoice.organizationId = "42f929b1-8fdb-45b1-a7cf-34fae2314561"
    invoice.invoiceId = "inv-001"
    invoice.invoiceNumber = "INV-001"
    invoice.contactName = "Test Contact"
    invoice.contactId = "contact-123"
    invoice.invoiceDate = date(2024, 1, 15)
    invoice.dueDate = date(2024, 2, 15)
    invoice.status = InvoiceStatus.AUTHORISED
    invoice.lineAmountTypes = "Exclusive"
    invoice.subTotal = Decimal("100.00")
    invoice.totalTax = Decimal("10.00")
    invoice.total = Decimal("110.00")
    invoice.amountDue = Decimal("110.00")
    invoice.amountPaid = Decimal("0.00")
    invoice.amountCredited = Decimal("0.00")
    invoice.currencyCode = "AUD"
    invoice.reference = "Test Reference"
    invoice.brandId = None
    invoice.hasErrors = False
    invoice.isDiscounted = False
    invoice.hasAttachments = False
    invoice.sentToContact = True
    invoice.lastSyncedAt = datetime(2024, 1, 15, 10, 0, 0)
    invoice.xeroUpdatedDateUtc = None
    invoice.createdAt = datetime(2024, 1, 15, 9, 0, 0)
    invoice.updatedAt = datetime(2024, 1, 15, 9, 0, 0)
    return invoice


@pytest.fixture
def mock_invoice_list() -> List[Mock]:
    """List of mock Invoice objects for pagination testing."""
    invoices = []
    for i in range(3):
        invoice = Mock(spec=Invoice)
        invoice.id = f"test-invoice-id-{i}"
        invoice.organizationId = "42f929b1-8fdb-45b1-a7cf-34fae2314561"
        invoice.invoiceId = f"inv-00{i + 1}"
        invoice.invoiceNumber = f"INV-00{i + 1}"
        invoice.contactName = f"Test Contact {i + 1}"
        invoice.contactId = f"contact-{i + 1}"
        invoice.invoiceDate = date(2024, 1, 15 + i)
        invoice.dueDate = date(2024, 2, 15 + i)
        invoice.status = InvoiceStatus.AUTHORISED
        invoice.total = Decimal(f"{100 + i * 10}.00")
        invoice.amountDue = Decimal(f"{100 + i * 10}.00")
        invoice.amountPaid = Decimal("0.00")
        invoice.currencyCode = "AUD"
        invoice.reference = f"Test Reference {i + 1}"
        invoice.hasErrors = False
        invoice.createdAt = datetime(2024, 1, 15 + i, 9, 0, 0)
        invoice.updatedAt = datetime(2024, 1, 15 + i, 9, 0, 0)
        invoices.append(invoice)
    return invoices


class InvoiceTestData:
    """Helper class for generating consistent invoice test data."""

    @staticmethod
    def create_mock_invoice(
        invoice_id: str = "test-invoice-id",
        organization_id: str = "42f929b1-8fdb-45b1-a7cf-34fae2314561",
        status: InvoiceStatus = InvoiceStatus.AUTHORISED,
        total: Optional[Decimal] = None,
        contact_name: Optional[str] = None,
    ) -> Mock:
        """Create a mock invoice with custom parameters."""
        invoice = Mock(spec=Invoice)
        invoice.id = invoice_id
        invoice.organizationId = organization_id
        invoice.invoiceId = f"inv-{invoice_id[-3:]}"
        invoice.invoiceNumber = f"INV-{invoice_id[-3:]}"
        invoice.contactName = contact_name or "Test Contact"
        invoice.contactId = "contact-123"
        invoice.invoiceDate = date(2024, 1, 15)
        invoice.dueDate = date(2024, 2, 15)
        invoice.status = status
        invoice.total = total or Decimal("110.00")
        invoice.amountDue = total or Decimal("110.00")
        invoice.amountPaid = Decimal("0.00")
        invoice.currencyCode = "AUD"
        invoice.reference = "Test Reference"
        invoice.hasErrors = False
        invoice.createdAt = datetime(2024, 1, 15, 9, 0, 0)
        invoice.updatedAt = datetime(2024, 1, 15, 9, 0, 0)
        return invoice

    @staticmethod
    def pagination_test_data() -> dict:
        """Standard pagination test parameters."""
        return {
            "page": 1,
            "limit": 10,
            "total": 25,
            "pages": 3,
            "has_next": True,
            "has_prev": False,
        }
