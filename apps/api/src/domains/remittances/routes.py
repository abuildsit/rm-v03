from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Query, UploadFile, status
from prisma.models import OrganizationMember

from prisma import Prisma
from src.core.database import get_db
from src.domains.remittances.models import (
    FileUploadResponse,
    FileUrlResponse,
    RemittanceDetailResponse,
    RemittanceListResponse,
    RemittanceUpdateRequest,
)
from src.domains.remittances.service import (
    create_remittance,
    get_file_url,
    get_remittance_by_id,
    get_remittances_by_organization,
    update_remittance,
)
from src.shared.permissions import Permission, require_permission

router = APIRouter(prefix="/remittances", tags=["Remittances"])


@router.post(
    "/{org_id}",
    response_model=FileUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload remittance file",
    description="Upload a new remittance PDF file for processing",
)
async def upload_remittance(
    org_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="PDF file to upload"),
    membership: OrganizationMember = Depends(
        require_permission(Permission.CREATE_REMITTANCES)
    ),
    db: Prisma = Depends(get_db),
) -> FileUploadResponse:
    """
    Upload a new remittance file.

    Requires CREATE_REMITTANCES permission.
    Only PDF files up to 10MB are allowed.
    """
    remittance = await create_remittance(
        db=db,
        org_id=org_id,
        user_id=membership.profileId or "",
        file=file,
        background_tasks=background_tasks,
    )

    return FileUploadResponse(
        message="File uploaded successfully",
        remittance_id=remittance.id,
        filename=remittance.filename,
        file_path=remittance.file_path or "",
    )


@router.get(
    "/{org_id}",
    response_model=RemittanceListResponse,
    status_code=status.HTTP_200_OK,
    summary="List remittances",
    description="Get paginated list of remittances with optional filtering",
)
async def list_remittances(
    org_id: str,
    page: int = Query(1, description="Page number for pagination", ge=1, le=1000),
    page_size: int = Query(50, description="Number of records per page", ge=1, le=500),
    status_filter: Optional[str] = Query(
        None, description="Filter by remittance status"
    ),
    date_from: Optional[str] = Query(
        None, description="Filter remittances from this date (ISO format)"
    ),
    date_to: Optional[str] = Query(
        None, description="Filter remittances to this date (ISO format)"
    ),
    search: Optional[str] = Query(
        None, description="Search in filename or payment reference"
    ),
    membership: OrganizationMember = Depends(
        require_permission(Permission.VIEW_REMITTANCES)
    ),
    db: Prisma = Depends(get_db),
) -> RemittanceListResponse:
    """
    Get a paginated list of remittances for the organization.

    Requires VIEW_REMITTANCES permission.
    Supports filtering by status, date range, and text search.
    """
    return await get_remittances_by_organization(
        db=db,
        org_id=org_id,
        page=page,
        page_size=page_size,
        status_filter=status_filter,
        date_from=date_from,
        date_to=date_to,
        search=search,
    )


@router.get(
    "/{org_id}/{remittance_id}",
    response_model=RemittanceDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get remittance details",
    description=(
        "Get detailed information about a specific remittance including its lines"
    ),
)
async def get_remittance(
    org_id: str,
    remittance_id: str,
    membership: OrganizationMember = Depends(
        require_permission(Permission.VIEW_REMITTANCES)
    ),
    db: Prisma = Depends(get_db),
) -> RemittanceDetailResponse:
    """
    Get detailed information about a specific remittance.

    Requires VIEW_REMITTANCES permission.
    Returns remittance data including associated remittance lines.
    """
    return await get_remittance_by_id(db=db, org_id=org_id, remittance_id=remittance_id)


@router.patch(
    "/{org_id}/{remittance_id}",
    response_model=RemittanceDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Update remittance",
    description="Update remittance details, approve matches, or perform soft deletion",
)
async def update_remittance_endpoint(
    org_id: str,
    remittance_id: str,
    update_data: RemittanceUpdateRequest,
    membership: OrganizationMember = Depends(
        require_permission(Permission.MANAGE_REMITTANCES)
    ),
    db: Prisma = Depends(get_db),
) -> RemittanceDetailResponse:
    """
    Update a remittance record.

    Requires MANAGE_REMITTANCES permission.
    Can be used for:
    - Updating basic remittance details
    - Approving matches (status transitions)
    - Soft deletion
    """
    return await update_remittance(
        db=db,
        org_id=org_id,
        user_id=membership.profileId or "",
        remittance_id=remittance_id,
        update_data=update_data,
    )


@router.get(
    "/{org_id}/{remittance_id}/file",
    response_model=FileUrlResponse,
    status_code=status.HTTP_200_OK,
    summary="Get remittance file URL",
    description="Get a temporary signed URL for accessing the remittance file",
)
async def get_remittance_file_url(
    org_id: str,
    remittance_id: str,
    membership: OrganizationMember = Depends(
        require_permission(Permission.VIEW_REMITTANCES)
    ),
    db: Prisma = Depends(get_db),
) -> FileUrlResponse:
    """
    Get a signed URL for accessing the remittance file.

    Requires VIEW_REMITTANCES permission.
    Returns a temporary URL that expires in 1 hour.
    """
    return await get_file_url(db=db, org_id=org_id, remittance_id=remittance_id)
