import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, cast

from fastapi import HTTPException, UploadFile, status
from prisma.enums import AuditAction, AuditOutcome, RemittanceStatus
from prisma.types import RemittanceUpdateInput, RemittanceWhereInput
from supabase import create_client

from prisma import Prisma
from src.core.settings import settings
from src.domains.remittances.models import (
    FileUrlResponse,
    RemittanceDetailResponse,
    RemittanceListResponse,
    RemittanceResponse,
    RemittanceUpdateRequest,
)

# Initialize Supabase client
supabase = create_client(
    settings.SUPABASE_URL or "", settings.SUPABASE_SERVICE_ROLE_KEY or ""
)

BUCKET_NAME = "remittances"
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_TYPES = ["application/pdf"]


async def validate_file(file: UploadFile) -> None:
    """Validate uploaded file type and size."""
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Only PDF files are allowed"
        )

    if file.size is not None and file.size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"File size exceeds maximum limit of "
                f"{MAX_FILE_SIZE / (1024*1024):.0f}MB"
            ),
        )


def generate_file_path(org_id: str) -> tuple[str, str]:
    """Generate unique file path with format: {org_id}/{year}/{month}/{uuid}"""
    now = datetime.now(timezone.utc)
    unique_id = str(uuid.uuid4())
    file_path = f"{org_id}/{now.year}/{now.month:02d}/{unique_id}"
    return file_path, unique_id


async def upload_file_to_storage(file: UploadFile, file_path: str, org_id: str) -> str:
    """Upload file to Supabase Storage and return the stored path."""
    try:
        # Read file content
        file_content = await file.read()

        # Upload to Supabase Storage
        response = supabase.storage.from_(BUCKET_NAME).upload(
            path=file_path,
            file=file_content,
            file_options={
                "content-type": file.content_type or "application/pdf",
                "cache-control": "3600",
            },
        )

        if response.error:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to upload file: {response.error.message}",
            )

        return file_path

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"File upload failed: {str(e)}",
        )


async def create_remittance(
    db: Prisma, org_id: str, user_id: str, file: UploadFile
) -> RemittanceResponse:
    """Create a new remittance record with file upload."""
    # Validate file
    await validate_file(file)

    # Generate file path
    file_path, unique_id = generate_file_path(org_id)

    # Upload file to storage
    stored_path = await upload_file_to_storage(file, file_path, org_id)

    try:
        # Create remittance record
        remittance = await db.remittance.create(
            data={
                "organizationId": org_id,
                "filename": file.filename or f"remittance_{unique_id}.pdf",
                "filePath": stored_path,
                "status": RemittanceStatus.Uploaded,
            }
        )

        # Create audit log
        await db.auditlog.create(
            data={
                "remittanceId": remittance.id,
                "userId": user_id,
                "organizationId": org_id,
                "action": AuditAction.created,
                "outcome": AuditOutcome.success,
                "newValue": RemittanceStatus.Uploaded.value,
            }
        )

        return RemittanceResponse.model_validate(remittance)

    except Exception as e:
        # Clean up uploaded file if database operation fails
        try:
            supabase.storage.from_(BUCKET_NAME).remove([stored_path])
        except Exception:
            pass  # Don't fail if cleanup fails

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create remittance record: {str(e)}",
        )


async def get_remittances_by_organization(
    db: Prisma,
    org_id: str,
    page: int = 1,
    page_size: int = 50,
    status_filter: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    search: Optional[str] = None,
) -> RemittanceListResponse:
    """Get paginated list of remittances with optional filtering."""
    # Build where clause
    where_clause: Dict[str, Any] = {"organizationId": org_id}

    if status_filter:
        try:
            status_enum = RemittanceStatus(status_filter)
            where_clause["status"] = status_enum
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status filter: {status_filter}",
            )

    if date_from:
        try:
            from_date = datetime.fromisoformat(date_from.replace("Z", "+00:00"))
            where_clause["createdAt"] = {"gte": from_date}
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid date_from format. Use ISO format.",
            )

    if date_to:
        try:
            to_date = datetime.fromisoformat(date_to.replace("Z", "+00:00"))
            if "createdAt" in where_clause:
                where_clause["createdAt"].update({"lte": to_date})
            else:
                where_clause["createdAt"] = {"lte": to_date}
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid date_to format. Use ISO format.",
            )

    if search:
        where_clause["OR"] = [
            {"filename": {"contains": search, "mode": "insensitive"}},
            {"reference": {"contains": search, "mode": "insensitive"}},
        ]

    # Calculate offset
    offset = (page - 1) * page_size

    # Get total count
    total = await db.remittance.count(where=cast(RemittanceWhereInput, where_clause))

    # Get remittances
    remittances = await db.remittance.find_many(
        where=cast(RemittanceWhereInput, where_clause),
        skip=offset,
        take=page_size,
        order={"createdAt": "desc"},
    )

    # Calculate pagination info
    total_pages = (total + page_size - 1) // page_size

    return RemittanceListResponse(
        remittances=[RemittanceResponse.model_validate(r) for r in remittances],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


async def get_remittance_by_id(
    db: Prisma, org_id: str, remittance_id: str
) -> RemittanceDetailResponse:
    """Get a single remittance with its lines."""
    remittance = await db.remittance.find_unique(
        where={"id": remittance_id}, include={"lines": True}
    )

    if not remittance or remittance.organizationId != org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Remittance not found"
        )

    return RemittanceDetailResponse.model_validate(remittance)


async def update_remittance(
    db: Prisma,
    org_id: str,
    user_id: str,
    remittance_id: str,
    update_data: RemittanceUpdateRequest,
) -> RemittanceDetailResponse:
    """Update a remittance record."""
    # Get existing remittance
    existing = await db.remittance.find_unique(where={"id": remittance_id})

    if not existing or existing.organizationId != org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Remittance not found"
        )

    # Prepare update data
    update_dict = {}
    for field, value in update_data.model_dump(exclude_unset=True).items():
        if field == "is_deleted" and value:
            # Handle soft deletion
            # Note: Prisma schema doesn't show deletedAt field, so we might
            # need to add it
            # For now, we could use a status or add the field to schema
            continue
        else:
            # Convert snake_case to camelCase for Prisma
            if field == "payment_date":
                update_dict["paymentDate"] = value
            elif field == "total_amount":
                update_dict["totalAmount"] = value
            else:
                update_dict[field] = value

    if not update_dict:
        # Return existing remittance if no updates
        return await get_remittance_by_id(db, org_id, remittance_id)

    # Update remittance
    remittance = await db.remittance.update(
        where={"id": remittance_id},
        data=cast(RemittanceUpdateInput, update_dict),
        include={"lines": True},
    )

    # Create audit log for significant changes
    if "status" in update_dict:
        action = (
            AuditAction.approved
            if update_dict["status"] == RemittanceStatus.Awaiting_Approval
            else AuditAction.updated
        )
        await db.auditlog.create(
            data={
                "remittanceId": remittance_id,
                "userId": user_id,
                "organizationId": org_id,
                "action": action,
                "outcome": AuditOutcome.success,
                "fieldChanged": "status",
                "oldValue": existing.status.value,
                "newValue": (
                    update_dict["status"].value
                    if isinstance(update_dict["status"], RemittanceStatus)
                    else str(update_dict["status"])
                ),
            }
        )

    return RemittanceDetailResponse.model_validate(remittance)


async def get_file_url(db: Prisma, org_id: str, remittance_id: str) -> FileUrlResponse:
    """Get a signed URL for accessing the remittance file."""
    # Get remittance
    remittance = await db.remittance.find_unique(where={"id": remittance_id})

    if not remittance or remittance.organizationId != org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Remittance not found"
        )

    if not remittance.filePath:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="File not found"
        )

    try:
        # Generate signed URL (expires in 1 hour)
        response = supabase.storage.from_(BUCKET_NAME).create_signed_url(
            path=remittance.filePath, expires_in=3600
        )

        if response.get("error"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to generate file URL: {response['error']['message']}",
            )

        return FileUrlResponse(url=response["signedURL"], expires_in=3600)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate file URL: {str(e)}",
        )
