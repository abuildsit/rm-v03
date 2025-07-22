"""Generic type definitions for external accounting integrations."""

from typing import Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field

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
