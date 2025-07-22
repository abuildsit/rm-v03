from typing import Dict, List

from fastapi import APIRouter, Depends
from prisma.models import OrganizationMember

from prisma import Prisma
from src.core.database import get_db
from src.domains.bankaccounts.models import (
    BankAccountResponse,
    BankAccountSaveResponse,
)
from src.domains.bankaccounts.service import (
    get_bank_accounts_by_organization,
    update_bank_accounts_by_organization,
)
from src.shared.permissions import Permission, require_permission

# Create router with prefix and tags
router = APIRouter(prefix="/bankaccounts", tags=["Bank Accounts"])


@router.get(
    "/{org_id}",
    response_model=List[BankAccountResponse],
    operation_id="getBankAccounts",
)
async def get_bank_accounts(
    org_id: str,
    membership: OrganizationMember = Depends(
        require_permission(Permission.VIEW_BANK_ACCOUNTS)
    ),
    db: Prisma = Depends(get_db),
) -> List[BankAccountResponse]:
    """
    Get bank accounts for a specific organization

    Requires VIEW_BANK_ACCOUNTS permission.
    All organization members can view bank accounts.
    """
    # Get bank accounts using the service
    return await get_bank_accounts_by_organization(str(org_id), db)


@router.post(
    "/{org_id}",
    response_model=BankAccountSaveResponse,
    operation_id="updateBankAccounts",
)
async def update_bank_accounts(
    org_id: str,
    request: Dict,
    membership: OrganizationMember = Depends(
        require_permission(Permission.MANAGE_BANK_ACCOUNTS)
    ),
    db: Prisma = Depends(get_db),
) -> BankAccountSaveResponse:
    """
    Update bank accounts for a specific organization

    Requires MANAGE_BANK_ACCOUNTS permission.
    Updates enablePaymentsToAccount and isDefault settings.
    """
    # Update bank accounts using the service
    return await update_bank_accounts_by_organization(str(org_id), request, db)
