from typing import Dict, List

from fastapi import HTTPException, status

from prisma import Prisma
from src.domains.bankaccounts.models import (
    BankAccountResponse,
    BankAccountSaveRequest,
    BankAccountSaveResponse,
)


async def get_bank_accounts_by_organization(
    organization_id: str, db: Prisma
) -> List[BankAccountResponse]:
    """
    Get bank accounts for an organization

    Args:
        organization_id: Organization ID to filter by
        db: Prisma database connection

    Returns:
        List[BankAccountResponse] with account details
    """
    # Get bank accounts for the organization
    accounts = await db.bankaccount.find_many(
        where={"organizationId": organization_id},
        order={"createdAt": "desc"},  # Consistent ordering
    )

    # Convert to response models
    account_responses = [
        BankAccountResponse.from_prisma(account) for account in accounts
    ]

    return account_responses


async def update_bank_accounts_by_organization(
    organization_id: str, request: Dict, db: Prisma
) -> BankAccountSaveResponse:
    """
    Update bank accounts for an organization

    Args:
        organization_id: Organization ID to filter by
        request: Update request data
        db: Prisma database connection

    Returns:
        BankAccountSaveResponse with update results

    Raises:
        HTTPException: If validation fails or accounts don't exist
    """
    # Parse the request data
    save_request = BankAccountSaveRequest(**request)

    # Validate organization ID matches
    if save_request.organizationId != organization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization ID mismatch",
        )

    # Validate business rules
    await _validate_update_request(save_request, organization_id, db)

    # Perform updates in a transaction
    try:
        updated_accounts = []
        async with db.tx() as transaction:
            for account_update in save_request.accounts:
                # Update the account
                updated_account = await transaction.bankaccount.update(
                    where={"id": account_update.accountId},
                    data={
                        "enablePaymentsToAccount": (
                            account_update.enablePaymentsToAccount
                        ),
                        "isDefault": account_update.isDefault,
                    },
                )
                updated_accounts.append(updated_account)

            # If setting a new default, unset any other defaults
            for account_update in save_request.accounts:
                if account_update.isDefault:
                    await transaction.bankaccount.update_many(
                        where={
                            "organizationId": organization_id,
                            "id": {"not": account_update.accountId},
                        },
                        data={"isDefault": False},
                    )

        # Calculate saved accounts count (enablePaymentsToAccount=True)
        saved_accounts = sum(
            1 for account in save_request.accounts if account.enablePaymentsToAccount
        )

        return BankAccountSaveResponse(
            success=True,
            message="Bank accounts updated successfully",
            savedAccounts=saved_accounts,
            accounts=save_request.accounts,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update bank accounts: {str(e)}",
        )


async def _validate_update_request(
    request: BankAccountSaveRequest, organization_id: str, db: Prisma
) -> None:
    """
    Validate the update request for business rules

    Args:
        request: The update request to validate
        organization_id: Organization ID for validation
        db: Prisma database connection

    Raises:
        HTTPException: If validation fails
    """
    # Check for multiple defaults
    default_count = sum(1 for account in request.accounts if account.isDefault)
    if default_count > 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only one account can be set as default",
        )

    # Validate all account IDs exist and belong to the organization
    account_ids = [account.accountId for account in request.accounts]
    existing_accounts = await db.bankaccount.find_many(
        where={"id": {"in": account_ids}, "organizationId": organization_id}
    )

    existing_ids = {account.id for account in existing_accounts}
    missing_ids = set(account_ids) - existing_ids

    if missing_ids:
        missing_list = ", ".join(missing_ids)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid account ID(s): {missing_list}",
        )
