# apps/api/src/domains/invoices/models.py
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from prisma.enums import InvoiceStatus
from prisma.models import Invoice
from pydantic import BaseModel


class InvoiceResponse(BaseModel):
    """Response model for invoice data"""

    id: str
    organizationId: str
    invoiceId: str
    invoiceNumber: Optional[str] = None
    contactName: Optional[str] = None
    contactId: Optional[str] = None
    invoiceDate: Optional[date] = None
    dueDate: Optional[date] = None
    status: Optional[InvoiceStatus] = None
    lineAmountTypes: Optional[str] = None
    subTotal: Optional[Decimal] = None
    totalTax: Optional[Decimal] = None
    total: Optional[Decimal] = None
    amountDue: Optional[Decimal] = None
    amountPaid: Optional[Decimal] = None
    amountCredited: Optional[Decimal] = None
    currencyCode: Optional[str] = None
    reference: Optional[str] = None
    brandId: Optional[str] = None
    hasErrors: Optional[bool] = None
    isDiscounted: Optional[bool] = None
    hasAttachments: Optional[bool] = None
    sentToContact: Optional[bool] = None
    lastSyncedAt: Optional[datetime] = None
    xeroUpdatedDateUtc: Optional[datetime] = None
    createdAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None

    @classmethod
    def from_prisma(cls, invoice: Invoice) -> "InvoiceResponse":
        return cls(
            id=invoice.id,
            organizationId=invoice.organizationId,
            invoiceId=invoice.invoiceId,
            invoiceNumber=invoice.invoiceNumber,
            contactName=invoice.contactName,
            contactId=invoice.contactId,
            invoiceDate=invoice.invoiceDate,
            dueDate=invoice.dueDate,
            status=invoice.status,
            lineAmountTypes=invoice.lineAmountTypes,
            subTotal=invoice.subTotal,
            totalTax=invoice.totalTax,
            total=invoice.total,
            amountDue=invoice.amountDue,
            amountPaid=invoice.amountPaid,
            amountCredited=invoice.amountCredited,
            currencyCode=invoice.currencyCode,
            reference=invoice.reference,
            brandId=invoice.brandId,
            hasErrors=invoice.hasErrors,
            isDiscounted=invoice.isDiscounted,
            hasAttachments=invoice.hasAttachments,
            sentToContact=invoice.sentToContact,
            lastSyncedAt=invoice.lastSyncedAt,
            xeroUpdatedDateUtc=invoice.xeroUpdatedDateUtc,
            createdAt=invoice.createdAt,
            updatedAt=invoice.updatedAt,
        )


class PaginationMetadata(BaseModel):
    """Pagination metadata for list responses"""

    page: int
    limit: int
    total: int
    pages: int
    has_next: bool
    has_prev: bool


class InvoiceListResponse(BaseModel):
    """Response model for invoice list with pagination"""

    invoices: List[InvoiceResponse]
    pagination: PaginationMetadata
