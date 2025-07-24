"""Xero API type definitions for type safety."""

from datetime import datetime
from decimal import Decimal
from typing import List, Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator


# Xero API Filter Types
class InvoiceFilters(BaseModel):
    """Filters for invoice queries."""

    status: Optional[List[str]] = Field(
        None, description="Invoice statuses to filter by"
    )
    date_from: Optional[datetime] = Field(
        None, description="Start date for invoice filtering"
    )
    date_to: Optional[datetime] = Field(
        None, description="End date for invoice filtering"
    )
    modified_since: Optional[datetime] = Field(
        None, description="Only invoices modified after this date"
    )


class AccountFilters(BaseModel):
    """Filters for account queries."""

    types: Optional[List[str]] = Field(None, description="Account types to filter by")


class PaymentData(BaseModel):
    """Payment data structure for creation."""

    invoice_id: str = Field(..., description="Invoice identifier")
    account_id: str = Field(..., description="Account identifier")
    amount: float = Field(..., description="Payment amount", gt=0)
    date: str = Field(..., description="Payment date in ISO format")
    reference: Optional[str] = Field(None, description="Payment reference")


# Xero API Response Types
class XeroContact(BaseModel):
    """Xero contact structure."""

    ContactID: str = Field(..., description="Xero contact identifier")
    Name: str = Field(..., description="Contact name")
    EmailAddress: Optional[str] = Field(None, description="Contact email address")
    ContactStatus: str = Field(..., description="Contact status in Xero")


class XeroLineItem(BaseModel):
    """Xero invoice line item structure."""

    LineItemID: Optional[str] = Field(None, description="Line item identifier")
    Description: str = Field(..., description="Line item description")
    UnitAmount: float = Field(..., description="Price per unit")
    Quantity: float = Field(..., description="Quantity of items")
    LineAmount: float = Field(..., description="Total line amount")
    TaxAmount: Optional[float] = Field(None, description="Tax amount for line")
    AccountCode: Optional[str] = Field(None, description="Account code for line")


class XeroInvoice(BaseModel):
    """Xero invoice structure."""

    InvoiceID: str = Field(..., description="Xero invoice identifier")
    InvoiceNumber: Optional[str] = Field(None, description="Invoice number")
    Type: Literal["ACCREC", "ACCPAY"] = Field(
        ..., description="Invoice type (receivable or payable)"
    )
    Contact: XeroContact = Field(..., description="Invoice contact information")
    Date: str = Field(..., description="Invoice date in Xero format")
    DueDate: Optional[str] = Field(None, description="Invoice due date")
    Status: Literal["DRAFT", "SUBMITTED", "AUTHORISED", "PAID", "VOIDED", "DELETED"] = (
        Field(..., description="Invoice status")
    )
    LineAmountTypes: Literal["Exclusive", "Inclusive", "NoTax"] = Field(
        ..., description="How line amounts are calculated"
    )
    SubTotal: float = Field(..., description="Invoice subtotal before tax")
    TotalTax: float = Field(..., description="Total tax amount")
    Total: float = Field(..., description="Total invoice amount including tax")
    AmountDue: Optional[float] = Field(None, description="Amount still due")
    AmountPaid: Optional[float] = Field(None, description="Amount already paid")
    AmountCredited: Optional[float] = Field(None, description="Amount credited")
    CurrencyCode: str = Field(..., description="Currency code (e.g., USD, AUD)")
    LineItems: List[XeroLineItem] = Field(..., description="Invoice line items")
    UpdatedDateUTC: Optional[str] = Field(None, description="Last updated date")
    CreatedDateUTC: Optional[str] = Field(None, description="Created date")
    BrandingThemeID: Optional[str] = Field(
        None, description="Branding theme identifier"
    )
    Reference: Optional[str] = Field(None, description="Invoice reference")


class XeroAccount(BaseModel):
    """Xero account structure."""

    AccountID: str = Field(..., description="Xero account identifier")
    Code: str = Field(..., description="Account code")
    Name: str = Field(..., description="Account name")
    Type: Literal[
        "BANK", "CURRENT", "FIXED", "EQUITY", "EXPENSE", "REVENUE", "LIABILITY"
    ] = Field(..., description="Account type")
    BankAccountType: Optional[Literal["BANK", "CREDITCARD", "PAYPAL"]] = Field(
        None, description="Bank account type"
    )
    BankAccountNumber: Optional[str] = Field(None, description="Bank account number")
    CurrencyCode: Optional[str] = Field(None, description="Currency code")
    TaxType: Optional[str] = Field(None, description="Tax type")
    EnablePaymentsToAccount: Optional[bool] = Field(
        None, description="Whether payments are enabled"
    )
    ShowInExpenseClaims: Optional[bool] = Field(
        None, description="Show in expense claims"
    )
    Class: Optional[Literal["ASSET", "EQUITY", "EXPENSE", "LIABILITY", "REVENUE"]] = (
        Field(None, description="Account class")
    )
    SystemAccount: Optional[str] = Field(None, description="System account identifier")
    ReportingCode: Optional[str] = Field(None, description="Reporting code")
    ReportingCodeName: Optional[str] = Field(None, description="Reporting code name")
    HasAttachments: Optional[bool] = Field(
        None, description="Whether account has attachments"
    )
    UpdatedDateUTC: Optional[str] = Field(None, description="Last updated date")


class XeroPayment(BaseModel):
    """Xero payment structure."""

    PaymentID: str = Field(..., description="Xero payment identifier")
    Date: str = Field(..., description="Payment date")
    Amount: float = Field(..., description="Payment amount")
    Reference: Optional[str] = Field(None, description="Payment reference")
    CurrencyRate: Optional[float] = Field(None, description="Currency exchange rate")
    PaymentType: Optional[Literal["ACCRECPAYMENT", "ACCPAYPAYMENT"]] = Field(
        None, description="Type of payment"
    )
    Status: Optional[Literal["AUTHORISED", "DELETED"]] = Field(
        None, description="Payment status"
    )
    UpdatedDateUTC: Optional[str] = Field(None, description="Last updated date")
    Account: Optional["XeroAccount"] = Field(None, description="Associated account")
    Invoice: Optional["XeroInvoice"] = Field(None, description="Associated invoice")


class XeroAttachment(BaseModel):
    """Xero attachment structure."""

    AttachmentID: str = Field(..., description="Xero attachment identifier")
    FileName: str = Field(..., description="File name")
    MimeType: str = Field(..., description="MIME type of file")
    Url: Optional[str] = Field(None, description="URL to access file")
    ContentLength: Optional[int] = Field(None, description="File size in bytes")
    IncludeOnline: Optional[bool] = Field(None, description="Whether to include online")


# Xero API Response Wrappers
class XeroInvoicesResponse(BaseModel):
    """Response wrapper for invoices endpoint."""

    Invoices: List[XeroInvoice] = Field(
        ..., description="List of invoices from Xero API"
    )


class XeroAccountsResponse(BaseModel):
    """Response wrapper for accounts endpoint."""

    Accounts: List[XeroAccount] = Field(
        ..., description="List of accounts from Xero API"
    )


class XeroPaymentsResponse(BaseModel):
    """Response wrapper for payments endpoint."""

    Payments: List[XeroPayment] = Field(
        ..., description="List of payments from Xero API"
    )


class XeroAttachmentsResponse(BaseModel):
    """Response wrapper for attachments endpoint."""

    Attachments: List[XeroAttachment] = Field(
        ..., description="List of attachments from Xero API"
    )


# HTTP Request Parameter Types
class HttpParams(BaseModel):
    """HTTP request parameters."""

    page: Optional[int] = Field(None, description="Page number for pagination")
    where: Optional[str] = Field(None, description="Filter conditions")
    order: Optional[str] = Field(None, description="Sort order specification")


# HTTP Headers type - using dict due to hyphenated header names
HttpHeaders = dict[str, str]


class HttpRequestKwargs(BaseModel):
    """HTTP request keyword arguments."""

    headers: Optional[HttpHeaders] = Field(None, description="Request headers")
    params: Optional[HttpParams] = Field(None, description="URL parameters")
    # json_data removed - use explicit request models instead
    files: Optional[dict[str, tuple[str, bytes]]] = Field(
        None, description="File uploads"
    )
    timeout: Optional[float] = Field(None, description="Request timeout in seconds")


# Batch Payment Types
class XeroInvoiceRef(BaseModel):
    """Reference to a Xero invoice for batch payments."""

    InvoiceID: str = Field(..., description="Xero invoice identifier")


class XeroAccountRef(BaseModel):
    """Reference to a Xero account for batch payments."""

    AccountID: str = Field(..., description="Xero account identifier")


class XeroBatchPaymentPayment(BaseModel):
    """Individual payment within a Xero batch payment."""

    Invoice: XeroInvoiceRef = Field(..., description="Invoice reference with InvoiceID")
    Amount: str = Field(..., description="Payment amount as string")
    Reference: Optional[str] = Field(None, description="Payment reference")

    @field_validator("Amount")
    @classmethod
    def validate_amount(cls, v: str) -> str:
        """Validate amount is not empty."""
        if not v.strip():
            raise ValueError("Amount cannot be empty")
        return v


class XeroBatchPaymentItem(BaseModel):
    """Individual batch payment response item."""

    BatchPaymentID: str = Field(..., description="Xero batch payment identifier")
    Account: Optional[XeroAccountRef] = Field(
        None, description="Associated account reference"
    )
    Date: Optional[str] = Field(None, description="Payment date")
    Reference: Optional[str] = Field(None, description="Payment reference")
    Status: Optional[Literal["AUTHORISED", "DELETED"]] = Field(
        None, description="Batch payment status"
    )
    TotalAmount: Optional[str] = Field(None, description="Total batch payment amount")
    UpdatedDateUTC: Optional[str] = Field(None, description="Last updated date")


class XeroBatchPaymentResponse(BaseModel):
    """Response wrapper for batch payments endpoint."""

    BatchPayments: List[XeroBatchPaymentItem] = Field(
        ..., description="List of batch payments from Xero API"
    )


class XeroBatchPaymentRequest(BaseModel):
    """Typed request structure for Xero batch payment API."""

    Account: XeroAccountRef = Field(..., description="Bank account for payment")
    Date: str = Field(..., description="Payment date in YYYY-MM-DD format")
    Reference: str = Field(..., description="Batch payment reference")
    Payments: List[XeroBatchPaymentPayment] = Field(..., description="List of payments")

    @field_validator("Date")
    @classmethod
    def validate_date_format(cls, v: str) -> str:
        """Validate date is in YYYY-MM-DD format."""
        import re

        if not re.match(r"^\d{4}-\d{2}-\d{2}$", v):
            raise ValueError("Date must be in YYYY-MM-DD format")
        return v

    @field_validator("Reference")
    @classmethod
    def validate_reference(cls, v: str) -> str:
        """Validate reference is not empty."""
        if not v.strip():
            raise ValueError("Reference cannot be empty")
        return v

    @field_validator("Payments")
    @classmethod
    def validate_payments(
        cls, v: List[XeroBatchPaymentPayment]
    ) -> List[XeroBatchPaymentPayment]:
        """Validate at least one payment is provided."""
        if not v:
            raise ValueError("At least one payment is required")
        return v


# Bank Transaction types
class XeroBankTransaction(BaseModel):
    """Xero bank transaction details."""

    BankTransactionID: str = Field(..., description="Xero bank transaction identifier")
    BatchPayment: Optional[dict] = Field(
        None, description="Batch payment reference if applicable"
    )
    Type: str = Field(..., description="Transaction type (SPEND, RECEIVE, etc.)")
    Status: str = Field(..., description="Transaction status (AUTHORISED, DELETED)")
    IsReconciled: bool = Field(..., description="Whether transaction is reconciled")
    Date: str = Field(..., description="Transaction date")
    Reference: Optional[str] = Field(None, description="Transaction reference")
    Total: Decimal = Field(..., description="Total transaction amount")
    UpdatedDateUTC: str = Field(..., description="Last modified date UTC")


class XeroBankTransactionsResponse(BaseModel):
    """Response wrapper for bank transactions endpoint."""

    BankTransactions: List[XeroBankTransaction] = Field(
        ..., description="List of bank transactions from Xero API"
    )


class BatchPaymentStatusResult(BaseModel):
    """Result of batch payment status check."""

    batch_id: str
    status: str  # AUTHORISED, DELETED
    is_reconciled: bool
    last_updated: str
    found: bool  # Whether the batch payment was found in Xero


# Union types for API responses
XeroApiResponse = Union[
    XeroInvoicesResponse,
    XeroAccountsResponse,
    XeroPaymentsResponse,
    XeroAttachmentsResponse,
    XeroBatchPaymentResponse,
    XeroBankTransactionsResponse,
]
