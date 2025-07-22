# apps/api/src/domains/external_accounting/xero/routes.py
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import RedirectResponse
from prisma.models import OrganizationMember, Profile

from prisma import Prisma
from src.core.database import get_db
from src.domains.auth.dependencies import get_current_profile
from src.shared.permissions import Permission, require_permission

from .models import (
    XeroAuthUrlResponse,
    XeroCallbackParams,
    XeroConnectionStatus,
    XeroDisconnectResponse,
)
from .service import XeroService

# Router for Xero integration endpoints
router = APIRouter(prefix="/external-accounting", tags=["External Accounting"])


@router.post(
    "/auth/xero/{org_id}",
    response_model=XeroAuthUrlResponse,
    status_code=status.HTTP_200_OK,
    operation_id="startXeroConnection",
)
async def start_xero_connection(
    org_id: UUID,
    membership: OrganizationMember = Depends(
        require_permission(Permission.MANAGE_INTEGRATIONS)
    ),
    profile: Profile = Depends(get_current_profile),
    db: Prisma = Depends(get_db),
) -> XeroAuthUrlResponse:
    """
    Start the Xero OAuth connection process for an organization.

    This endpoint generates an OAuth authorization URL that redirects users to Xero
    for authentication. The URL includes a JWT state token for security.

    **Permission Required**: MANAGE_INTEGRATIONS (Owner/Admin)

    **Business Rules**:
    - Cannot start connection if organization already has active Xero connection
    - State token expires in 30 minutes
    - CSRF protection via state parameter

    Args:
        org_id: Organization ID to connect

    Returns:
        Authorization URL and expiry time for frontend redirection

    Raises:
        HTTP 400: If organization already has active connection
        HTTP 500: If OAuth URL generation fails
    """
    service = XeroService(db)
    return await service.start_connection(str(org_id), profile.id)


@router.get(
    "/auth/xero/callback",
    operation_id="xeroOAuthCallback",
)
async def xero_oauth_callback(
    code: str = Query(None, description="OAuth authorization code"),
    state: str = Query(None, description="JWT state token"),
    error: str = Query(None, description="OAuth error code"),
    error_description: str = Query(None, description="OAuth error description"),
    db: Prisma = Depends(get_db),
) -> RedirectResponse:
    """
    Handle the OAuth callback from Xero after user authorization.

    This endpoint completes the OAuth flow by exchanging the authorization code
    for access tokens and storing the connection details in the database.

    **No authentication required** - callback from external service

    **Redirect Behavior**:
    - Success: `/dashboard?xero_connected=true&tenant_name={name}`
    - Error: `/dashboard?error={error_type}&message={description}`

    Args:
        code: Authorization code from Xero (success case)
        state: JWT state token for validation
        error: Error code if authorization failed
        error_description: Human-readable error description

    Returns:
        RedirectResponse to frontend dashboard with status parameters
    """
    # Parse callback parameters
    callback_params = XeroCallbackParams(
        code=code,
        state=state,
        error=error,
        error_description=error_description,
    )

    try:
        # Handle OAuth errors first
        if error:
            error_msg = error_description or error
            return RedirectResponse(
                url=f"/dashboard?error=oauth_failed&message={error_msg}",
                status_code=status.HTTP_302_FOUND,
            )

        # Validate required parameters
        if not code or not state:
            return RedirectResponse(
                url=(
                    "/dashboard?error=invalid_callback&"
                    "message=Missing required parameters"
                ),
                status_code=status.HTTP_302_FOUND,
            )

        # Complete the connection
        service = XeroService(db)
        connection_response = await service.complete_connection(callback_params)

        # Trigger initial sync (non-blocking)
        import asyncio

        asyncio.create_task(_initial_sync(connection_response.organization_id, db))

        # Redirect to dashboard with success
        return RedirectResponse(
            url=(
                f"/dashboard?xero_connected=true&"
                f"tenant_name={connection_response.tenant_name}"
            ),
            status_code=status.HTTP_302_FOUND,
        )

    except Exception as e:
        # Handle any other errors with generic redirect
        error_message = str(e) if hasattr(e, "detail") else "Connection failed"
        return RedirectResponse(
            url=f"/dashboard?error=connection_failed&message={error_message}",
            status_code=status.HTTP_302_FOUND,
        )


@router.get(
    "/auth/xero/{org_id}",
    response_model=XeroConnectionStatus,
    operation_id="getXeroConnectionStatus",
)
async def get_xero_connection_status(
    org_id: UUID,
    membership: OrganizationMember = Depends(
        require_permission(Permission.VIEW_INTEGRATIONS)
    ),
    db: Prisma = Depends(get_db),
) -> XeroConnectionStatus:
    """
    Get the current Xero connection status for an organization.

    Returns detailed information about the connection state, including
    token expiry, last refresh times, and any error conditions.

    **Permission Required**: VIEW_INTEGRATIONS (Owner/Admin/Auditor)

    Args:
        org_id: Organization ID to check

    Returns:
        Detailed connection status information

    **Status Values**:
    - `connected`: Active connection with valid token
    - `expired`: Connection exists but token expired
    - `revoked`: Connection manually disconnected
    - `error`: Connection failed or token refresh failed
    - `disconnected`: No connection exists
    """
    service = XeroService(db)
    return await service.get_connection_status(str(org_id))


@router.patch(
    "/auth/xero/{org_id}",
    response_model=XeroDisconnectResponse,
    operation_id="disconnectXero",
)
async def disconnect_xero(
    org_id: UUID,
    membership: OrganizationMember = Depends(
        require_permission(Permission.MANAGE_INTEGRATIONS)
    ),
    db: Prisma = Depends(get_db),
) -> XeroDisconnectResponse:
    """
    Disconnect the Xero integration for an organization.

    This endpoint revokes the OAuth connection both locally and in Xero,
    preventing further API access. The connection record is preserved
    for audit purposes but marked as revoked.

    **Permission Required**: MANAGE_INTEGRATIONS (Owner/Admin)

    **Operations Performed**:
    1. Revoke connection in Xero (best effort)
    2. Update local connection status to 'revoked'
    3. Preserve audit trail

    Args:
        org_id: Organization ID to disconnect

    Returns:
        Confirmation with disconnection timestamp

    Raises:
        HTTP 404: If no Xero connection exists for organization
        HTTP 500: If disconnection operation fails

    **Note**: Even if Xero revocation fails, local disconnection will succeed
    to ensure users can always disconnect integrations.
    """
    service = XeroService(db)
    return await service.disconnect(str(org_id))


async def _initial_sync(org_id: str, db: Prisma) -> None:
    """
    Perform initial sync of accounts and invoices after Xero connection.

    This runs in the background and does not block the callback response.
    Syncs accounts first (typically faster), then invoices.

    Args:
        org_id: Organization ID
        db: Database connection
    """
    import logging

    from src.domains.external_accounting.base import (
        IntegrationFactory,
        SyncOrchestrator,
    )

    logger = logging.getLogger(__name__)

    try:
        factory = IntegrationFactory(db)
        data_service = await factory.get_data_service(org_id)
        orchestrator = SyncOrchestrator(db)

        # Sync accounts first (usually smaller dataset)
        logger.info(f"Starting initial account sync for organization {org_id}")
        account_result = await orchestrator.sync_accounts(
            data_service=data_service, org_id=org_id
        )

        if account_result.success:
            logger.info(
                f"Initial account sync completed for {org_id}: "
                f"{account_result.count} accounts in "
                f"{account_result.duration_seconds:.1f}s"
            )
        else:
            logger.error(
                f"Initial account sync failed for {org_id}: {account_result.error}"
            )

        # Sync last 12 months of invoices
        logger.info(f"Starting initial invoice sync for organization {org_id}")
        invoice_result = await orchestrator.sync_invoices(
            data_service=data_service, org_id=org_id, incremental=False, months_back=12
        )

        if invoice_result.success:
            logger.info(
                f"Initial invoice sync completed for {org_id}: "
                f"{invoice_result.count} invoices in "
                f"{invoice_result.duration_seconds:.1f}s"
            )
        else:
            logger.error(
                f"Initial invoice sync failed for {org_id}: {invoice_result.error}"
            )

    except Exception as e:
        logger.error(f"Initial sync failed for {org_id}: {e}", exc_info=True)
