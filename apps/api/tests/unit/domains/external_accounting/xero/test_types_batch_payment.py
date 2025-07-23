"""
Tests for Xero-specific batch payment types.
"""

import pytest
from pydantic import ValidationError

from src.domains.external_accounting.xero.types import (
    XeroAccountRef,
    XeroBatchPaymentPayment,
    XeroBatchPaymentRequest,
    XeroBatchPaymentResponse,
    XeroInvoiceRef,
)


class TestXeroBatchPaymentPayment:
    """Test XeroBatchPaymentPayment model."""

    def test_xero_batch_payment_payment_valid(self) -> None:
        """Test valid Xero batch payment payment creation."""
        payment = XeroBatchPaymentPayment(
            Invoice=XeroInvoiceRef(InvoiceID="test-invoice-123"),
            Amount="150.00",
            Reference="RM: Payment for Invoice INV-001",
        )

        assert payment.Invoice.InvoiceID == "test-invoice-123"
        assert payment.Amount == "150.00"
        assert payment.Reference == "RM: Payment for Invoice INV-001"

    def test_xero_batch_payment_payment_missing_invoice(self) -> None:
        """Test payment without invoice raises ValidationError."""
        with pytest.raises(ValidationError):
            XeroBatchPaymentPayment(
                Invoice=None,
                Amount="150.00",
                Reference="RM: Payment for Invoice INV-001",
            )

    def test_xero_batch_payment_payment_missing_amount(self) -> None:
        """Test payment without amount raises ValidationError."""
        with pytest.raises(ValidationError):
            XeroBatchPaymentPayment(
                Invoice=XeroInvoiceRef(InvoiceID="test-invoice-123"),
                Amount="",
                Reference="RM: Payment for Invoice INV-001",
            )

    def test_xero_batch_payment_payment_optional_reference(self) -> None:
        """Test payment with optional reference."""
        payment = XeroBatchPaymentPayment(
            Invoice=XeroInvoiceRef(InvoiceID="test-invoice-123"),
            Amount="150.00",
            Reference=None,
        )

        assert payment.Reference is None


class TestXeroBatchPaymentRequest:
    """Test XeroBatchPaymentRequest model."""

    def test_xero_batch_payment_request_valid(self) -> None:
        """Test valid Xero batch payment request creation."""
        batch_payment = XeroBatchPaymentRequest(
            Account=XeroAccountRef(AccountID="test-account-123"),
            Date="2024-01-15",
            Reference="RM: Batch Payment REF-12345",
            Payments=[
                XeroBatchPaymentPayment(
                    Invoice=XeroInvoiceRef(InvoiceID="test-invoice-1"),
                    Amount="150.00",
                    Reference="RM: Payment for Invoice INV-001",
                ),
                XeroBatchPaymentPayment(
                    Invoice=XeroInvoiceRef(InvoiceID="test-invoice-2"),
                    Amount="250.50",
                    Reference="RM: Payment for Invoice INV-002",
                ),
            ],
        )

        assert batch_payment.Account.AccountID == "test-account-123"
        assert batch_payment.Date == "2024-01-15"
        assert batch_payment.Reference == "RM: Batch Payment REF-12345"
        assert len(batch_payment.Payments) == 2
        assert batch_payment.Payments[0].Amount == "150.00"

    def test_xero_batch_payment_missing_account(self) -> None:
        """Test batch payment without account raises ValidationError."""
        with pytest.raises(ValidationError):
            XeroBatchPaymentRequest(
                Account=None,
                Date="2024-01-15",
                Reference="RM: Batch Payment REF-12345",
                Payments=[],
            )

    def test_xero_batch_payment_invalid_date_format(self) -> None:
        """Test batch payment with invalid date format raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            XeroBatchPaymentRequest(
                Account=XeroAccountRef(AccountID="test-account-123"),
                Date="15/01/2024",  # Invalid format for Xero
                Reference="RM: Batch Payment REF-12345",
                Payments=[],
            )

        assert "Date must be in YYYY-MM-DD format" in str(exc_info.value)

    def test_xero_batch_payment_empty_payments(self) -> None:
        """Test batch payment with empty payments list raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            XeroBatchPaymentRequest(
                Account=XeroAccountRef(AccountID="test-account-123"),
                Date="2024-01-15",
                Reference="RM: Batch Payment REF-12345",
                Payments=[],
            )

        assert "At least one payment is required" in str(exc_info.value)

    def test_xero_batch_payment_missing_reference(self) -> None:
        """Test batch payment without reference raises ValidationError."""
        with pytest.raises(ValidationError):
            XeroBatchPaymentRequest(
                Account=XeroAccountRef(AccountID="test-account-123"),
                Date="2024-01-15",
                Reference="",
                Payments=[
                    XeroBatchPaymentPayment(
                        Invoice=XeroInvoiceRef(InvoiceID="test-invoice-1"),
                        Amount="150.00",
                        Reference="RM: Payment for Invoice INV-001",
                    )
                ],
            )


class TestXeroBatchPaymentResponse:
    """Test XeroBatchPaymentResponse model."""

    def test_xero_batch_payment_response_valid(self) -> None:
        """Test valid Xero batch payment response parsing."""
        response_data = {
            "BatchPayments": [
                {
                    "BatchPaymentID": "test-batch-123",
                    "Account": {"AccountID": "test-account-123"},
                    "Date": "2024-01-15",
                    "Reference": "RM: Batch Payment REF-12345",
                    "Status": "AUTHORISED",
                    "TotalAmount": "400.50",
                    "UpdatedDateUTC": "2024-01-15T10:30:00Z",
                }
            ]
        }

        response = XeroBatchPaymentResponse(**response_data)
        assert len(response.BatchPayments) == 1
        assert response.BatchPayments[0].BatchPaymentID == "test-batch-123"
        assert response.BatchPayments[0].Status == "AUTHORISED"

    def test_xero_batch_payment_response_empty_list(self) -> None:
        """Test Xero batch payment response with empty BatchPayments list."""
        response_data = {"BatchPayments": []}

        response = XeroBatchPaymentResponse(**response_data)
        assert len(response.BatchPayments) == 0

    def test_xero_batch_payment_response_missing_batch_payment_id(self) -> None:
        """Test response with missing BatchPaymentID."""
        response_data = {
            "BatchPayments": [
                {
                    "Account": {"AccountID": "test-account-123"},
                    "Date": "2024-01-15",
                    "Reference": "RM: Batch Payment REF-12345",
                    "Status": "AUTHORISED",
                }
            ]
        }

        with pytest.raises(ValidationError):
            XeroBatchPaymentResponse(**response_data)

    def test_xero_batch_payment_response_multiple_batch_payments(self) -> None:
        """Test response with multiple batch payments (edge case)."""
        response_data = {
            "BatchPayments": [
                {
                    "BatchPaymentID": "test-batch-123",
                    "Account": {"AccountID": "test-account-123"},
                    "Date": "2024-01-15",
                    "Reference": "RM: Batch Payment REF-12345",
                    "Status": "AUTHORISED",
                },
                {
                    "BatchPaymentID": "test-batch-456",
                    "Account": {"AccountID": "test-account-123"},
                    "Date": "2024-01-16",
                    "Reference": "RM: Batch Payment REF-67890",
                    "Status": "AUTHORISED",
                },
            ]
        }

        response = XeroBatchPaymentResponse(**response_data)
        assert len(response.BatchPayments) == 2
        assert response.BatchPayments[0].BatchPaymentID == "test-batch-123"
        assert response.BatchPayments[1].BatchPaymentID == "test-batch-456"
