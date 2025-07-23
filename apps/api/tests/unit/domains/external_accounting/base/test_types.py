"""
Tests for base external accounting types including batch payment models.
"""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.domains.external_accounting.base.types import (
    BatchPaymentData,
    BatchPaymentResult,
    PaymentItem,
)


class TestPaymentItem:
    """Test PaymentItem model validation."""

    def test_payment_item_valid(self) -> None:
        """Test valid payment item creation."""
        payment_item = PaymentItem(
            invoice_id="test-invoice-123",
            amount=Decimal("150.00"),
            reference="Payment for Invoice INV-001",
        )

        assert payment_item.invoice_id == "test-invoice-123"
        assert payment_item.amount == Decimal("150.00")
        assert payment_item.reference == "Payment for Invoice INV-001"

    def test_payment_item_invalid_amount_zero(self) -> None:
        """Test payment item with zero amount raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            PaymentItem(
                invoice_id="test-invoice-123",
                amount=Decimal("0.00"),
                reference="Payment for Invoice INV-001",
            )

        assert "Input should be greater than 0" in str(exc_info.value)

    def test_payment_item_invalid_amount_negative(self) -> None:
        """Test payment item with negative amount raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            PaymentItem(
                invoice_id="test-invoice-123",
                amount=Decimal("-50.00"),
                reference="Payment for Invoice INV-001",
            )

        assert "Input should be greater than 0" in str(exc_info.value)

    def test_payment_item_missing_invoice_id(self) -> None:
        """Test payment item without invoice_id raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            PaymentItem(
                invoice_id="",
                amount=Decimal("150.00"),
                reference="Payment for Invoice INV-001",
            )

        assert "Invoice ID cannot be empty" in str(exc_info.value)

    def test_payment_item_missing_reference(self) -> None:
        """Test payment item without reference raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            PaymentItem(
                invoice_id="test-invoice-123", amount=Decimal("150.00"), reference=""
            )

        assert "Reference cannot be empty" in str(exc_info.value)


class TestBatchPaymentData:
    """Test BatchPaymentData model validation."""

    def test_batch_payment_data_valid(self) -> None:
        """Test valid batch payment data creation."""
        batch_data = BatchPaymentData(
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

        assert batch_data.account_id == "test-account-123"
        assert batch_data.payment_date == "2024-01-15"
        assert batch_data.payment_reference == "RM: Batch Payment REF-12345"
        assert len(batch_data.payments) == 2
        assert batch_data.payments[0].amount == Decimal("150.00")

    def test_batch_payment_data_missing_account_id(self) -> None:
        """Test batch payment data without account_id raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            BatchPaymentData(
                account_id="",
                payment_date="2024-01-15",
                payment_reference="RM: Batch Payment REF-12345",
                payments=[],
            )

        assert "Account ID cannot be empty" in str(exc_info.value)

    def test_batch_payment_data_invalid_date_format(self) -> None:
        """Test batch payment data with invalid date format raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            BatchPaymentData(
                account_id="test-account-123",
                payment_date="15/01/2024",  # Invalid format
                payment_reference="RM: Batch Payment REF-12345",
                payments=[],
            )

        assert "Date must be in YYYY-MM-DD format" in str(exc_info.value)

    def test_batch_payment_data_empty_payments(self) -> None:
        """Test batch payment data with empty payments list raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            BatchPaymentData(
                account_id="test-account-123",
                payment_date="2024-01-15",
                payment_reference="RM: Batch Payment REF-12345",
                payments=[],
            )

        assert "At least one payment is required" in str(exc_info.value)

    def test_batch_payment_data_missing_reference(self) -> None:
        """Test batch payment data without reference raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            BatchPaymentData(
                account_id="test-account-123",
                payment_date="2024-01-15",
                payment_reference="",
                payments=[
                    PaymentItem(
                        invoice_id="test-invoice-1",
                        amount=Decimal("150.00"),
                        reference="RM: Payment for Invoice INV-001",
                    )
                ],
            )

        assert "Payment reference cannot be empty" in str(exc_info.value)


class TestBatchPaymentResult:
    """Test BatchPaymentResult model."""

    def test_batch_payment_result_success(self) -> None:
        """Test successful batch payment result."""
        result = BatchPaymentResult(
            success=True, batch_id="test-batch-123", error_message=None
        )

        assert result.success is True
        assert result.batch_id == "test-batch-123"
        assert result.error_message is None

    def test_batch_payment_result_failure(self) -> None:
        """Test failed batch payment result."""
        result = BatchPaymentResult(
            success=False, batch_id=None, error_message="Invoice not found"
        )

        assert result.success is False
        assert result.batch_id is None
        assert result.error_message == "Invoice not found"

    def test_batch_payment_result_success_without_batch_id(self) -> None:
        """Test successful result requires batch_id."""
        with pytest.raises(ValidationError) as exc_info:
            BatchPaymentResult(success=True, batch_id=None, error_message=None)

        assert "Batch ID is required for successful payments" in str(exc_info.value)

    def test_batch_payment_result_failure_without_error(self) -> None:
        """Test failed result requires error_message."""
        with pytest.raises(ValidationError) as exc_info:
            BatchPaymentResult(success=False, batch_id=None, error_message=None)

        assert "Error message is required for failed payments" in str(exc_info.value)
