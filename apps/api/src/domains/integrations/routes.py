import asyncio
import logging

from fastapi import APIRouter, Depends
from prisma.models import OrganizationMember

from prisma import Prisma
from src.core.database import get_db
from src.shared.permissions import Permission, require_permission

from .base import IntegrationFactory, SyncOrchestrator, SyncResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/integrations", tags=["integrations"])


@router.post("/invoices/{org_id}", response_model=SyncResult)
async def sync_invoices(
    org_id: str,
    incremental: bool = True,
    months_back: int = 12,
    membership: OrganizationMember = Depends(
        require_permission(Permission.SYNC_INVOICES)
    ),
    db: Prisma = Depends(get_db),
) -> SyncResult:
    """
    Trigger invoice synchronization from accounting provider.

    Requires SYNC_INVOICES permission.

    Args:
        org_id: Organization ID
        incremental: If True, only sync invoices modified since last sync
        months_back: Number of months back to sync (if not incremental)
        membership: Validated organization membership with permissions
        db: Database connection

    Returns:
        SyncResult indicating that sync has been initiated
    """
    asyncio.create_task(_perform_invoice_sync(db, org_id, incremental, months_back))

    return SyncResult(
        object_type="invoices",
        success=True,
        count=0,
        duration_seconds=0.0,
    )


@router.post("/accounts/{org_id}", response_model=SyncResult)
async def sync_accounts(
    org_id: str,
    membership: OrganizationMember = Depends(
        require_permission(Permission.MANAGE_BANK_ACCOUNTS)
    ),
    db: Prisma = Depends(get_db),
) -> SyncResult:
    """
    Trigger bank account synchronization from accounting provider.

    Requires MANAGE_BANK_ACCOUNTS permission.

    Args:
        org_id: Organization ID
        membership: Validated organization membership with permissions
        db: Database connection

    Returns:
        SyncResult indicating that sync has been initiated
    """
    asyncio.create_task(_perform_account_sync(db, org_id))

    return SyncResult(
        object_type="accounts",
        success=True,
        count=0,
        duration_seconds=0.0,
    )


async def _perform_invoice_sync(
    db: Prisma, org_id: str, incremental: bool, months_back: int
) -> None:
    """Perform the actual invoice sync in background."""
    try:
        factory = IntegrationFactory(db)
        data_service = await factory.get_data_service(org_id)
        orchestrator = SyncOrchestrator(db)

        result = await orchestrator.sync_invoices(
            data_service=data_service,
            org_id=org_id,
            incremental=incremental,
            months_back=months_back,
        )

        if result.success:
            logger.info(
                f"Invoice sync completed for {org_id}: "
                f"{result.count} invoices in {result.duration_seconds:.1f}s"
            )
        else:
            logger.error(f"Invoice sync failed for {org_id}: {result.error}")

    except Exception as e:
        logger.error(f"Invoice sync failed for {org_id}: {e}", exc_info=True)


async def _perform_account_sync(db: Prisma, org_id: str) -> None:
    """Perform the actual account sync in background."""
    try:
        factory = IntegrationFactory(db)
        data_service = await factory.get_data_service(org_id)
        orchestrator = SyncOrchestrator(db)

        result = await orchestrator.sync_accounts(
            data_service=data_service, org_id=org_id
        )

        if result.success:
            logger.info(
                f"Account sync completed for {org_id}: "
                f"{result.count} accounts in {result.duration_seconds:.1f}s"
            )
        else:
            logger.error(f"Account sync failed for {org_id}: {result.error}")

    except Exception as e:
        logger.error(f"Account sync failed for {org_id}: {e}", exc_info=True)
