# apps/api/src/domains/invoices/routes.py
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from prisma.enums import InvoiceStatus
from prisma.models import Profile

from prisma import Prisma
from src.core.database import get_db
from src.domains.auth.dependencies import get_current_profile
from src.domains.auth.service import validate_organization_access
from src.domains.invoices.models import InvoiceListResponse
from src.domains.invoices.service import get_invoices_by_organization

# Create router with prefix and tags
router = APIRouter(prefix="/invoices", tags=["Invoices"])


@router.get(
    "/{org_id}",
    response_model=InvoiceListResponse,
    operation_id="getInvoices",
)
async def get_invoices(
    org_id: str,
    profile: Profile = Depends(get_current_profile),
    db: Prisma = Depends(get_db),
    page: int = Query(1, description="Page number for pagination", ge=1, le=1000),
    limit: int = Query(50, description="Number of records per page", ge=1, le=500),
    status: Optional[InvoiceStatus] = Query(
        None, description="Filter by invoice status"
    ),
    date_from: Optional[date] = Query(
        None, description="Filter invoices from this date (YYYY-MM-DD)"
    ),
    date_to: Optional[date] = Query(
        None, description="Filter invoices to this date (YYYY-MM-DD)"
    ),
    modified_since: Optional[datetime] = Query(
        None, description="Only return invoices modified since this date"
    ),
    contact_id: Optional[str] = Query(
        None, description="Filter by specific contact ID"
    ),
    search: Optional[str] = Query(
        None, description="Search in invoice number, contact name, or reference"
    ),
) -> InvoiceListResponse:
    """
    Get invoices for a specific organization with filtering and pagination

    Requires active membership in the specified organization.
    """
    # Validate user has access to the organization
    await validate_organization_access(profile.id, org_id, db)

    # Get invoices using the service
    return await get_invoices_by_organization(
        organization_id=org_id,
        db=db,
        page=page,
        limit=limit,
        status=status,
        date_from=date_from,
        date_to=date_to,
        modified_since=modified_since,
        contact_id=contact_id,
        search=search,
    )
