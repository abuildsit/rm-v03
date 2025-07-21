# apps/api/src/domains/invoices/service.py
import math
from datetime import date, datetime
from typing import Optional

from prisma import Prisma
from prisma.enums import InvoiceStatus
from prisma.types import InvoiceWhereInput
from src.domains.invoices.models import (
    InvoiceListResponse,
    InvoiceResponse,
    PaginationMetadata,
)


async def get_invoices_by_organization(
    organization_id: str,
    db: Prisma,
    page: int = 1,
    limit: int = 50,
    status: Optional[InvoiceStatus] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    modified_since: Optional[datetime] = None,
    contact_id: Optional[str] = None,
    search: Optional[str] = None,
) -> InvoiceListResponse:
    """
    Get invoices for an organization with filtering and pagination

    Args:
        organization_id: Organization ID to filter by
        db: Prisma database connection
        page: Page number (1-based)
        limit: Number of records per page
        status: Filter by invoice status
        date_from: Filter invoices from this date
        date_to: Filter invoices to this date
        modified_since: Only return invoices modified since this date
        contact_id: Filter by specific contact ID
        search: Search in invoice number, contact name, or reference

    Returns:
        InvoiceListResponse with invoices and pagination metadata
    """
    # Calculate offset for pagination
    offset = (page - 1) * limit

    # Build where clause
    where_input: InvoiceWhereInput = {
        "organizationId": organization_id,
    }

    # Add optional filters
    if status:
        where_input["status"] = status

    if date_from:
        if "invoiceDate" not in where_input:
            where_input["invoiceDate"] = {}
        where_input["invoiceDate"]["gte"] = date_from  # type: ignore[index]

    if date_to:
        if "invoiceDate" not in where_input:
            where_input["invoiceDate"] = {}
        where_input["invoiceDate"]["lte"] = date_to  # type: ignore[index]

    if modified_since:
        if "updatedAt" not in where_input:
            where_input["updatedAt"] = {}
        where_input["updatedAt"]["gte"] = modified_since  # type: ignore[index]

    if contact_id:
        where_input["contactId"] = contact_id

    if search:
        # Search across multiple fields using OR condition
        where_input["OR"] = [
            {"invoiceNumber": {"contains": search, "mode": "insensitive"}},
            {"contactName": {"contains": search, "mode": "insensitive"}},
            {"reference": {"contains": search, "mode": "insensitive"}},
        ]

    # Get invoices with pagination
    invoices = await db.invoice.find_many(
        where=where_input,
        skip=offset,
        take=limit,
        order={"createdAt": "desc"},  # Consistent ordering
    )

    # Get total count for pagination metadata
    total = await db.invoice.count(where=where_input)

    # Calculate pagination metadata
    total_pages = math.ceil(total / limit) if total > 0 else 1
    has_next = page * limit < total
    has_prev = page > 1

    pagination = PaginationMetadata(
        page=page,
        limit=limit,
        total=total,
        pages=total_pages,
        has_next=has_next,
        has_prev=has_prev,
    )

    # Convert to response models
    invoice_responses = [InvoiceResponse.from_prisma(invoice) for invoice in invoices]

    return InvoiceListResponse(
        invoices=invoice_responses,
        pagination=pagination,
    )
