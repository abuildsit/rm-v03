"""Generic type definitions for external accounting integrations."""

from decimal import Decimal
from typing import Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field, ValidationInfo, field_validator

# Generic type variables for different data types
InvoiceData = TypeVar("InvoiceData")
AccountData = TypeVar("AccountData")
PaymentData = TypeVar("PaymentData")
AttachmentData = TypeVar("AttachmentData")


# Generic filter types
class BaseFilters(BaseModel):
    """Base filter structure that all providers should support."""

    modified_since: Optional[str] = Field(
        None, description="ISO datetime string for filtering by modification date"
    )


class BaseInvoiceFilters(BaseFilters):
    """Base invoice filter structure."""

    status: Optional[List[str]] = Field(
        None, description="Invoice statuses to filter by"
    )
    date_from: Optional[str] = Field(
        None, description="Start date as ISO datetime string"
    )
    date_to: Optional[str] = Field(None, description="End date as ISO datetime string")


class BaseAccountFilters(BaseFilters):
    """Base account filter structure."""

    types: Optional[List[str]] = Field(None, description="Account types to filter by")


# Sync operation types
class SyncOptions(BaseModel):
    """Options for sync operations."""

    incremental: Optional[bool] = Field(
        None, description="Whether to perform incremental sync"
    )
    months_back: Optional[int] = Field(
        None, description="Number of months back to sync"
    )
    batch_size: Optional[int] = Field(
        None, description="Size of batches for processing"
    )


class MappingResult(BaseModel):
    """Result of data mapping operations."""

    success: bool = Field(..., description="Whether the mapping was successful")
    mapped_data: dict[str, str | int | float | bool | None] = Field(
        ..., description="The mapped data result"
    )
    errors: List[str] = Field(
        default_factory=list, description="List of mapping errors"
    )


# Type aliases for provider data - more flexible than protocols
ProviderInvoiceData = dict[str, str | int | float | bool | None]
ProviderAccountData = dict[str, str | int | float | bool | None]
ProviderPaymentData = dict[str, str | int | float | bool | None]
ProviderAttachmentData = dict[str, str | int | float | bool | None]


# Generic sync data containers
class SyncDataContainer(Generic[InvoiceData, AccountData]):
    """Generic container for sync operation data."""

    def __init__(
        self,
        invoices: List[InvoiceData] | None = None,
        accounts: List[AccountData] | None = None,
    ):
        self.invoices = invoices or []
        self.accounts = accounts or []


# Update operation types
class UpdateData(BaseModel):
    """Data structure for database updates."""

    create_data: Optional[dict[str, str | int | float | bool | None]] = Field(
        None, description="Data for creating new records"
    )
    update_data: Optional[dict[str, str | int | float | bool | None]] = Field(
        None, description="Data for updating existing records"
    )
    external_id: Optional[str] = Field(None, description="External system identifier")


class BatchUpdateResult(BaseModel):
    """Result of batch update operations."""

    created_count: int = Field(..., description="Number of records created")
    updated_count: int = Field(..., description="Number of records updated")
    error_count: int = Field(..., description="Number of errors encountered")
    errors: List[str] = Field(
        default_factory=list, description="List of error messages"
    )


# Batch payment types
class PaymentItem(BaseModel):
    """Individual payment item within a batch payment."""

    invoice_id: str = Field(..., description="Invoice identifier to pay")
    amount: Decimal = Field(..., description="Payment amount", gt=0)
    reference: str = Field(..., description="Payment reference")

    @field_validator("invoice_id")
    @classmethod
    def validate_invoice_id(cls, v: str) -> str:
        """Validate invoice_id is not empty."""
        if not v.strip():
            raise ValueError("Invoice ID cannot be empty")
        return v

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: Decimal) -> Decimal:
        """Validate amount is greater than zero."""
        if v <= 0:
            raise ValueError("Amount must be greater than zero")
        return v

    @field_validator("reference")
    @classmethod
    def validate_reference(cls, v: str) -> str:
        """Validate reference is not empty."""
        if not v.strip():
            raise ValueError("Reference cannot be empty")
        return v


class BatchPaymentData(BaseModel):
    """Provider-agnostic batch payment data structure."""

    account_id: str = Field(..., description="Bank account identifier")
    payment_date: str = Field(..., description="Payment date in YYYY-MM-DD format")
    payment_reference: str = Field(..., description="Overall batch payment reference")
    payments: List[PaymentItem] = Field(..., description="List of individual payments")

    @field_validator("account_id")
    @classmethod
    def validate_account_id(cls, v: str) -> str:
        """Validate account_id is not empty."""
        if not v.strip():
            raise ValueError("Account ID cannot be empty")
        return v

    @field_validator("payment_date")
    @classmethod
    def validate_payment_date(cls, v: str) -> str:
        """Validate payment_date is in YYYY-MM-DD format."""
        import re

        if not re.match(r"^\d{4}-\d{2}-\d{2}$", v):
            raise ValueError("Date must be in YYYY-MM-DD format")
        return v

    @field_validator("payment_reference")
    @classmethod
    def validate_payment_reference(cls, v: str) -> str:
        """Validate payment_reference is not empty."""
        if not v.strip():
            raise ValueError("Payment reference cannot be empty")
        return v

    @field_validator("payments")
    @classmethod
    def validate_payments(cls, v: List[PaymentItem]) -> List[PaymentItem]:
        """Validate at least one payment is provided."""
        if not v:
            raise ValueError("At least one payment is required")
        return v


class BatchPaymentResult(BaseModel):
    """Result of batch payment creation."""

    success: bool = Field(..., description="Whether the batch payment was successful")
    batch_id: Optional[str] = Field(
        None, description="Provider batch payment identifier"
    )
    error_message: Optional[str] = Field(None, description="Error message if failed")

    @field_validator("batch_id")
    @classmethod
    def validate_batch_id_on_success(
        cls, v: Optional[str], info: ValidationInfo
    ) -> Optional[str]:
        """Validate batch_id is provided for successful payments."""
        if info.data.get("success") and not v:
            raise ValueError("Batch ID is required for successful payments")
        return v

    @field_validator("error_message")
    @classmethod
    def validate_error_message_on_failure(
        cls, v: Optional[str], info: ValidationInfo
    ) -> Optional[str]:
        """Validate error_message is provided for failed payments."""
        if not info.data.get("success") and not v:
            raise ValueError("Error message is required for failed payments")
        return v
