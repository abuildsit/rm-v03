import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, cast

from fastapi import BackgroundTasks, HTTPException, UploadFile, status
from prisma.enums import AuditAction, AuditOutcome, RemittanceStatus
from prisma.types import RemittanceUpdateInput, RemittanceWhereInput
from supabase import create_client

from prisma import Json, Prisma
from src.core.settings import settings
from src.domains.external_accounting.base.data_service import BaseIntegrationDataService
from src.domains.external_accounting.base.factory import IntegrationFactory
from src.domains.external_accounting.base.sync_orchestrator import SyncOrchestrator
from src.domains.external_accounting.base.types import (
    BaseInvoiceFilters,
    BatchPaymentData,
    PaymentItem,
)

# storage_service import removed - using existing supabase client
from src.domains.remittances.ai_extraction import AIExtractionService
from src.domains.remittances.matching import MatchingService
from src.domains.remittances.models import (
    FileUrlResponse,
    RemittanceDetailResponse,
    RemittanceListResponse,
    RemittanceResponse,
    RemittanceUpdateRequest,
)

logger = logging.getLogger(__name__)

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


async def upload_file_to_storage_with_content(
    file_content: bytes, file_path: str, content_type: str | None
) -> str:
    """Upload file content to Supabase Storage and return the stored path."""
    try:
        # Upload to Supabase Storage
        response = supabase.storage.from_(BUCKET_NAME).upload(
            path=file_path,
            file=file_content,
            file_options={
                "content-type": content_type or "application/pdf",
                "cache-control": "3600",
            },
        )

        if hasattr(response, "error") and response.error:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to upload file: {response.error.message}",
            )
        elif isinstance(response, dict) and response.get("error"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to upload file: {response['error']['message']}",
            )

        return file_path

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"File upload failed: {str(e)}",
        )


async def create_remittance(
    db: Prisma,
    org_id: str,
    user_id: str,
    file: UploadFile,
    background_tasks: BackgroundTasks,
) -> RemittanceResponse:
    """Create a new remittance record with file upload."""
    # Validate file
    await validate_file(file)

    # Generate file path
    file_path, unique_id = generate_file_path(org_id)

    # Read file content once for both upload and processing
    file_content = await file.read()

    # Upload file to storage
    stored_path = await upload_file_to_storage_with_content(
        file_content, file_path, file.content_type
    )

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

        # Start background processing
        print(f"🎯 Adding background task for remittance {remittance.id}")
        print(f"📄 File content length: {len(file_content)} bytes")
        background_tasks.add_task(
            process_remittance_background,
            db,
            remittance.id,
            file_content,
            org_id,
            user_id,
        )
        print("✅ Background task added to queue")

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
    status_filter: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    search: str | None = None,
) -> RemittanceListResponse:
    """Get paginated list of remittances with optional filtering."""
    # Build where clause
    where_clause: dict[str, Any] = {"organizationId": org_id}

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
                existing_filter = where_clause["createdAt"]
                if isinstance(existing_filter, dict):
                    existing_filter.update({"lte": to_date})
                else:
                    where_clause["createdAt"] = {"lte": to_date}
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

    # Check if this is an approval action (status change to Exporting from
    # Awaiting_Approval)
    is_approval_action = (
        "status" in update_data.model_dump(exclude_unset=True)
        and update_data.status == RemittanceStatus.Exporting
        and existing.status == RemittanceStatus.Awaiting_Approval
    )

    # If this is an approval action, use the dedicated approve_remittance function
    if is_approval_action:
        return await approve_remittance(db, org_id, user_id, remittance_id)

    # Prepare update data for regular updates
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
                "oldValue": existing.status,
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


async def process_remittance_background(
    db: Prisma, remittance_id: str, file_content: bytes, org_id: str, user_id: str
) -> None:
    """
    Background task to process remittance: extract data and match invoices.
    """
    # Write directly to stderr to ensure visibility
    import sys

    print(
        f"🚀 BACKGROUND TASK STARTED for remittance {remittance_id}",
        file=sys.stderr,
        flush=True,
    )
    print(
        f"📊 File content size: {len(file_content)} bytes", file=sys.stderr, flush=True
    )

    # Also update status immediately to confirm task is running
    await db.remittance.update(
        where={"id": remittance_id}, data={"status": RemittanceStatus.Processing}
    )
    print(
        f"✅ Updated status to Processing for {remittance_id}",
        file=sys.stderr,
        flush=True,
    )

    try:
        logger.info(f"Starting background processing for remittance {remittance_id}")

        print("🔧 Initializing AI extraction service...", file=sys.stderr, flush=True)
        # Initialize services
        ai_service = AIExtractionService()
        print("✅ AI service initialized", file=sys.stderr, flush=True)

        print("🔧 Initializing matching service...", file=sys.stderr, flush=True)
        matching_service = MatchingService(db)
        print("✅ Matching service initialized", file=sys.stderr, flush=True)

        from uuid import UUID

        print("🤖 Starting AI extraction from PDF...", file=sys.stderr, flush=True)

        # Create AI client instance to check for thread ID after creation
        from src.shared.ai import openai_client

        try:
            # Extract data using AI
            extracted_data = await ai_service.extract_from_pdf(
                pdf_content=file_content, organization_id=UUID(org_id)
            )

            # Check if we have a thread ID from the client and save it immediately
            current_thread_id = (
                openai_client.get_current_thread_id()
                if openai_client
                else extracted_data.thread_id
            )
            if current_thread_id:
                print(
                    f"💾 Saving thread ID {current_thread_id} for debugging",
                    file=sys.stderr,
                    flush=True,
                )
                await db.remittance.update(
                    where={"id": remittance_id},
                    data={"openaiThreadId": current_thread_id},
                )
                print(
                    f"✅ Thread ID {current_thread_id} saved to database",
                    file=sys.stderr,
                    flush=True,
                )

            print(
                "🎉 AI extraction completed successfully!", file=sys.stderr, flush=True
            )
        except Exception as ai_error:
            # Try to save thread ID even if extraction fails
            current_thread_id = (
                openai_client.get_current_thread_id() if openai_client else None
            )
            if current_thread_id:
                print(
                    f"💾 Saving thread ID {current_thread_id} despite "
                    f"extraction failure",
                    file=sys.stderr,
                    flush=True,
                )
                await db.remittance.update(
                    where={"id": remittance_id},
                    data={"openaiThreadId": current_thread_id},
                )
                print(
                    f"✅ Thread ID {current_thread_id} saved for debugging",
                    file=sys.stderr,
                    flush=True,
                )

            # Re-raise the original error
            raise ai_error

        # Store the raw JSON output for debugging and auditing
        import json

        raw_json_string = json.dumps(
            extracted_data.model_dump(mode="json"), default=str, indent=2
        )

        # Update remittance with basic extracted data
        await db.remittance.update(
            where={"id": remittance_id},
            data={
                "status": RemittanceStatus.Data_Retrieved,
                "totalAmount": extracted_data.total_amount,
                "paymentDate": datetime.combine(
                    extracted_data.payment_date, datetime.min.time(), timezone.utc
                ),
                "reference": extracted_data.payment_reference,
                "confidenceScore": extracted_data.confidence,
                # Thread ID already saved above, but include here as backup
                "openaiThreadId": extracted_data.thread_id,
                # Store raw extracted JSON for debugging
                "extractedRawJson": cast(Json, raw_json_string),
            },
        )

        print(
            f"✅ Remittance {remittance_id} updated with extracted data",
            file=sys.stderr,
            flush=True,
        )

        # Create remittance lines from extracted payment data
        print(
            f"📝 Creating {len(extracted_data.payments)} remittance lines...",
            file=sys.stderr,
            flush=True,
        )

        for payment in extracted_data.payments:
            try:
                # Use proper Prisma types for create operation
                from prisma.types import RemittanceLineCreateInput

                create_data: RemittanceLineCreateInput = {
                    "remittanceId": remittance_id,
                    "invoiceNumber": payment.invoice_number,
                    "aiPaidAmount": payment.paid_amount,
                    # Initialize matching fields as None - will be set during
                    # invoice matching
                    "aiInvoiceId": None,
                    "overrideInvoiceId": None,
                    "matchConfidence": None,
                    "matchType": None,
                }

                await db.remittanceline.create(data=create_data)
                print(
                    f"✅ Created line for invoice {payment.invoice_number} "
                    f"with amount {payment.paid_amount}",
                    file=sys.stderr,
                    flush=True,
                )
            except Exception as line_error:
                print(
                    f"❌ Failed to create line for invoice "
                    f"{payment.invoice_number}: {line_error}",
                    file=sys.stderr,
                    flush=True,
                )
                # Log the error but continue with other lines
                logger.warning(
                    f"Failed to create remittance line for invoice "
                    f"{payment.invoice_number}: {line_error}"
                )

        print(
            f"✅ Completed remittance line creation for {remittance_id}",
            file=sys.stderr,
            flush=True,
        )

        # Start invoice matching process
        print(
            f"🔍 Starting invoice matching for {len(extracted_data.payments)} lines...",
            file=sys.stderr,
            flush=True,
        )

        try:
            # Get the created remittance lines to match them
            created_lines = await db.remittanceline.find_many(
                where={"remittanceId": remittance_id}, order={"createdAt": "asc"}
            )

            print(
                f"📋 Found {len(created_lines)} lines to match",
                file=sys.stderr,
                flush=True,
            )

            # Process each line for matching
            matched_count = 0
            for i, line in enumerate(created_lines, 1):
                print(
                    f"🎯 Matching line {i}/{len(created_lines)}: "
                    f"Invoice {line.invoiceNumber} (${line.aiPaidAmount})",
                    file=sys.stderr,
                    flush=True,
                )

                try:
                    # Create ExtractedPayment for the matching service
                    from src.domains.remittances.types import ExtractedPayment

                    # Skip lines without paid amount
                    if line.aiPaidAmount is None:
                        continue

                    payment = ExtractedPayment(
                        invoice_number=line.invoiceNumber, paid_amount=line.aiPaidAmount
                    )

                    # Use matching service to find matches
                    match_results, _ = (
                        await matching_service.match_payments_to_invoices(
                            payments=[payment],
                            organization_id=UUID(org_id),
                            remittance_id=UUID(remittance_id),
                        )
                    )

                    if match_results and len(match_results) > 0:
                        match = match_results[0]
                        match_type_str = (
                            match.match_type.value if match.match_type else "unknown"
                        )
                        print(
                            f"  ✅ MATCH FOUND: {line.invoiceNumber} → "
                            f"{match_type_str} match (confidence: "
                            f"{match.match_confidence})",
                            file=sys.stderr,
                            flush=True,
                        )

                        # Update the remittance line with match data using proper
                        # Prisma relations
                        from prisma.types import RemittanceLineUpdateInput

                        # Build update data with proper types from Prisma schema
                        update_data: RemittanceLineUpdateInput = {
                            "matchConfidence": match.match_confidence,
                            "matchType": (
                                match.match_type.value if match.match_type else None
                            ),
                        }

                        # Update aiInvoice relation using Prisma's connect operation
                        if match.matched_invoice_id:
                            update_data["aiInvoice"] = {
                                "connect": {"id": str(match.matched_invoice_id)}
                            }

                        await db.remittanceline.update(
                            where={"id": line.id},
                            data=update_data,
                        )
                        matched_count += 1
                        print(
                            "  💾 Updated line with match data",
                            file=sys.stderr,
                            flush=True,
                        )
                    else:
                        print(
                            f"  ❌ NO MATCH: {line.invoiceNumber}",
                            file=sys.stderr,
                            flush=True,
                        )

                except Exception as match_error:
                    print(
                        f"  ⚠️ Matching failed for {line.invoiceNumber}: {match_error}",
                        file=sys.stderr,
                        flush=True,
                    )
                    logger.warning(
                        f"Invoice matching failed for line {line.id}: {match_error}"
                    )

            # Update remittance status based on matching results
            match_percentage = (
                (matched_count / len(created_lines)) * 100 if created_lines else 0
            )

            print(
                f"📊 Matching complete: {matched_count}/{len(created_lines)} "
                f"lines matched ({match_percentage:.1f}%)",
                file=sys.stderr,
                flush=True,
            )

            # Determine final status based on match percentage
            if match_percentage == 100:
                final_status = RemittanceStatus.Awaiting_Approval
                status_msg = "All lines matched - awaiting approval"
            elif match_percentage > 0:
                final_status = RemittanceStatus.Partially_Matched
                status_msg = f"Partially matched ({match_percentage:.1f}%)"
            else:
                final_status = RemittanceStatus.Unmatched
                status_msg = "No matches found"

            # Update remittance with final status
            await db.remittance.update(
                where={"id": remittance_id}, data={"status": final_status}
            )

            print(
                f"🎉 Final status: {final_status.value} - {status_msg}",
                file=sys.stderr,
                flush=True,
            )

        except Exception as matching_error:
            print(
                f"❌ Invoice matching process failed: {matching_error}",
                file=sys.stderr,
                flush=True,
            )
            logger.error(
                f"Invoice matching failed for remittance {remittance_id}: "
                f"{matching_error}"
            )

            # Set status to manual review if matching fails
            await db.remittance.update(
                where={"id": remittance_id},
                data={"status": RemittanceStatus.Manual_Review},
            )

        logger.info(
            f"Completed processing remittance {remittance_id} with thread ID tracking"
        )

    except Exception as e:
        logger.error(
            f"Background processing failed for remittance {remittance_id}: {e}"
        )

        # Update status to failed
        await db.remittance.update(
            where={"id": remittance_id}, data={"status": RemittanceStatus.File_Error}
        )

        # Create error audit log
        await db.auditlog.create(
            data={
                "remittanceId": remittance_id,
                "userId": user_id,
                "organizationId": org_id,
                "action": AuditAction.sync_attempt,
                "outcome": AuditOutcome.error,
                "errorMessage": str(e),
            }
        )


async def approve_remittance(
    db: Prisma, org_id: str, user_id: str, remittance_id: str
) -> RemittanceDetailResponse:
    """
    Approve a remittance and create batch payment in external accounting system.

    Args:
        db: Database instance
        org_id: Organization ID
        user_id: User ID performing the approval
        remittance_id: Remittance ID to approve

    Returns:
        Updated remittance details

    Raises:
        HTTPException: If remittance not found, invalid status, or processing fails
    """
    # Get remittance with lines
    remittance = await db.remittance.find_unique(
        where={"id": remittance_id}, include={"lines": True}
    )

    if not remittance or remittance.organizationId != org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Remittance not found"
        )

    # Check if remittance is in correct status for approval
    if remittance.status != RemittanceStatus.Awaiting_Approval:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Remittance is not awaiting approval",
        )

    # Check if there are matched lines to process
    if not remittance.lines:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No remittance lines found",
        )

    matched_lines = [
        line
        for line in remittance.lines
        if line.aiInvoiceId is not None or line.overrideInvoiceId is not None
    ]

    if not matched_lines:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No matched lines found for payment",
        )

    # Get default bank account for the organization
    bank_account = await db.bankaccount.find_first(
        where={"organizationId": org_id, "isDefault": True}
    )

    if not bank_account:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No default bank account configured",
        )

    # Create audit log for approval start
    await db.auditlog.create(
        data={
            "remittanceId": remittance_id,
            "userId": user_id,
            "organizationId": org_id,
            "action": AuditAction.approved,
            "outcome": AuditOutcome.pending,
            "reason": "Remittance approval started",
        }
    )

    # Update status to Exporting
    await db.remittance.update(
        where={"id": remittance_id}, data={"status": RemittanceStatus.Exporting}
    )

    try:
        # Pre-download file content before batch payment creation
        file_content = None
        filename = None
        if remittance.filePath:
            try:
                file_content = supabase.storage.from_(BUCKET_NAME).download(
                    remittance.filePath
                )
                filename = f"Remittance_{remittance.reference or remittance.id}.pdf"
            except Exception as e:
                logger.warning(f"Failed to download remittance file: {e}")

        # Get matched invoices for creating batch payment
        invoice_ids = []
        for line in matched_lines:
            # Use override invoice if available, otherwise use AI match
            invoice_id = line.overrideInvoiceId or line.aiInvoiceId
            if invoice_id:
                invoice_ids.append(invoice_id)

        matched_invoices = await db.invoice.find_many(where={"id": {"in": invoice_ids}})

        # Build batch payment data
        batch_payment_data = _build_batch_payment_data(
            remittance, bank_account, matched_invoices
        )

        # Get external accounting data service
        factory = IntegrationFactory(db)
        data_service = await factory.get_data_service(org_id)

        # Create batch payment
        result = await data_service.create_batch_payment(org_id, batch_payment_data)

        if result.success:
            # Update remittance with batch ID and success status
            await db.remittance.update(
                where={"id": remittance_id},
                data={
                    "status": RemittanceStatus.Exported_Unreconciled,
                    "xeroBatchId": result.batch_id,
                },
            )

            # Create success audit log
            await db.auditlog.create(
                data={
                    "remittanceId": remittance_id,
                    "userId": user_id,
                    "organizationId": org_id,
                    "action": AuditAction.exported,
                    "outcome": AuditOutcome.success,
                    "reason": f"Batch payment created with ID: {result.batch_id}",
                }
            )

            # Schedule async file upload if file was downloaded successfully
            if file_content and filename and result.batch_id:
                batch_id = result.batch_id  # Ensure type is str

                async def upload_task() -> None:
                    try:
                        await data_service.upload_attachment(
                            org_id=org_id,
                            entity_id=batch_id,
                            entity_type="BankTransactions",
                            file_data=file_content,
                            filename=filename,
                        )
                        logger.info(
                            f"Uploaded remittance to batch payment {result.batch_id}"
                        )
                    except Exception as e:
                        logger.error(f"Failed to upload remittance attachment: {e}")

                asyncio.create_task(upload_task())

            # Schedule invoice sync task
            asyncio.create_task(
                _sync_batch_payment_invoices(db, org_id, matched_invoices, data_service)
            )

            logger.info(
                f"Successfully approved remittance {remittance_id} with batch "
                f"payment {result.batch_id}"
            )

        else:
            # Update status to failed
            await db.remittance.update(
                where={"id": remittance_id},
                data={"status": RemittanceStatus.Export_Failed, "xeroBatchId": None},
            )

            # Create failure audit log
            await db.auditlog.create(
                data={
                    "remittanceId": remittance_id,
                    "userId": user_id,
                    "organizationId": org_id,
                    "action": AuditAction.exported,
                    "outcome": AuditOutcome.error,
                    "errorMessage": result.error_message,
                    "reason": "Batch payment creation failed",
                }
            )

            logger.error(
                f"Failed to create batch payment for remittance {remittance_id}: "
                f"{result.error_message}"
            )

    except Exception as e:
        # Update status to failed
        await db.remittance.update(
            where={"id": remittance_id}, data={"status": RemittanceStatus.Export_Failed}
        )

        # Create error audit log
        await db.auditlog.create(
            data={
                "remittanceId": remittance_id,
                "userId": user_id,
                "organizationId": org_id,
                "action": AuditAction.exported,
                "outcome": AuditOutcome.error,
                "errorMessage": str(e),
                "reason": "Batch payment processing error",
            }
        )

        logger.error(f"Error during remittance approval {remittance_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process batch payment: {str(e)}",
        )

    # Return updated remittance details
    return await get_remittance_by_id(db, org_id, remittance_id)


def _build_batch_payment_data(
    remittance: Any, bank_account: Any, matched_invoices: list[Any]
) -> BatchPaymentData:
    """
    Build batch payment data from remittance and matched invoices.

    Args:
        remittance: Remittance object with lines
        bank_account: Bank account object
        matched_invoices: List of matched invoice objects

    Returns:
        BatchPaymentData for external accounting system
    """
    # Create invoice lookup map for efficient matching
    invoice_map = {invoice.id: invoice for invoice in matched_invoices}

    # Build payment items from matched lines
    payments = []

    for line in remittance.lines:
        # Use override invoice if available, otherwise use AI match
        invoice_id = line.overrideInvoiceId or line.aiInvoiceId
        if not invoice_id:
            continue

        # Get the matched invoice
        invoice = invoice_map.get(invoice_id)
        if not invoice:
            logger.warning(
                f"Invoice {invoice_id} not found for remittance line {line.id}"
            )
            continue

        # Use the paid amount from the line
        paid_amount = line.aiPaidAmount
        if paid_amount is None:
            logger.warning(f"No paid amount for remittance line {line.id}")
            continue

        # Create payment item
        payment_item = PaymentItem(
            invoice_id=invoice.invoiceId,  # Use Xero invoice ID
            amount=paid_amount,
            reference=f"RM: Payment for Invoice {line.invoiceNumber}",
        )
        payments.append(payment_item)

    # Build batch payment data
    return BatchPaymentData(
        account_id=bank_account.xeroAccountId,
        payment_date=(
            remittance.paymentDate.strftime("%Y-%m-%d")
            if remittance.paymentDate
            else datetime.now(timezone.utc).strftime("%Y-%m-%d")
        ),
        payment_reference=(
            f"RM: Batch Payment {remittance.reference or remittance.filename}"
        ),
        payments=payments,
    )


async def _sync_batch_payment_invoices(
    db: Prisma,
    org_id: str,
    matched_invoices: list[Any],
    data_service: BaseIntegrationDataService,
) -> None:
    """
    Sync invoice statuses after batch payment creation (async).

    Args:
        db: Database instance
        org_id: Organization ID
        matched_invoices: List of matched invoice objects
        data_service: External accounting data service
    """
    orchestrator = SyncOrchestrator(db)

    for invoice in matched_invoices:
        try:
            # Fetch updated invoice from Xero using the invoice_id parameter
            updated_invoices = await data_service.get_invoices(
                org_id=org_id,
                filters=BaseInvoiceFilters(
                    modified_since=None,
                    status=None,
                    date_from=None,
                    date_to=None,
                    invoice_id=None,
                ),
                invoice_id=invoice.invoiceId,  # Xero invoice ID
            )

            if updated_invoices:
                await orchestrator._upsert_invoices(org_id, updated_invoices)

        except Exception as e:
            logger.warning(f"Failed to sync invoice {invoice.invoiceId}: {e}")


async def sync_batch_payment_status(
    db: Prisma, org_id: str, remittance_id: str
) -> None:
    """
    Sync batch payment status from Xero for a remittance.

    This method checks the current status of the batch payment in Xero
    and updates the remittance record with the latest status and
    reconciliation info.

    Args:
        org_id: Organization ID
        remittance_id: Remittance ID to sync status for
    """
    try:
        # Get the remittance record
        remittance = await db.remittance.find_unique(where={"id": remittance_id})

        if not remittance or not remittance.xeroBatchId:
            logger.warning(f"No batch payment ID found for remittance {remittance_id}")
            return

        # Get external accounting data service
        from src.domains.external_accounting.base.factory import (
            IntegrationFactory,
        )

        factory = IntegrationFactory(db)
        data_service = await factory.get_data_service(org_id)

        if not data_service:
            logger.warning(f"No external accounting integration found for org {org_id}")
            return

        # Check if it's a Xero data service (type checking)
        if not hasattr(data_service, "get_batch_payment_status"):
            logger.warning(
                "Data service does not support batch payment status checking"
            )
            return

        # Get batch payment status from Xero (cast to specific type)
        from src.domains.external_accounting.xero.data_service import (
            XeroDataService,
        )

        xero_service = cast(XeroDataService, data_service)
        status_result = await xero_service.get_batch_payment_status(
            org_id, remittance.xeroBatchId
        )

        if not status_result.found:
            logger.warning(f"Batch payment {remittance.xeroBatchId} not found in Xero")
            return

        # Map Xero status to our enum
        from prisma.enums import BatchPaymentStatus

        batch_status = None
        if status_result.status == "AUTHORISED":
            batch_status = BatchPaymentStatus.AUTHORISED
        elif status_result.status == "DELETED":
            batch_status = BatchPaymentStatus.DELETED

        # Update remittance with current status
        from datetime import datetime, timezone

        await db.remittance.update(
            where={"id": remittance_id},
            data={
                "batchPaymentStatus": batch_status,
                "isReconciled": status_result.is_reconciled,
                "lastStatusCheck": datetime.now(timezone.utc),
            },
        )

        logger.info(
            f"Updated batch payment status for remittance {remittance_id}: "
            f"status={status_result.status}, "
            f"reconciled={status_result.is_reconciled}"
        )

    except Exception as e:
        logger.error(
            f"Failed to sync batch payment status for remittance "
            f"{remittance_id}: {e}"
        )


async def sync_all_pending_batch_payments(db: Prisma, org_id: str) -> None:
    """
    Sync status for all remittances with batch payments that need status updates.

    This method finds all remittances that have been exported but may
    need status updates, and syncs their batch payment status from Xero.

    Args:
        org_id: Organization ID
    """
    try:
        from datetime import datetime, timedelta, timezone

        from prisma.enums import RemittanceStatus

        # Find remittances that might need status updates:
        # 1. Have xeroBatchId (batch payment created)
        # 2. Status is Exported_Unreconciled or Exporting
        # 3. Haven't been checked recently (more than 1 hour ago)
        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)

        # Find remittances that might need status updates
        remittances = await db.remittance.find_many(
            where={
                "organizationId": org_id,
                "NOT": [{"xeroBatchId": None}],  # Has batch ID
            }
        )

        # Filter in Python for simplicity (avoiding complex Prisma typing)
        filtered_remittances = [
            r
            for r in remittances
            if r.status
            in [RemittanceStatus.Exported_Unreconciled, RemittanceStatus.Exporting]
            and (r.lastStatusCheck is None or r.lastStatusCheck < one_hour_ago)
        ]

        logger.info(f"Found {len(filtered_remittances)} remittances to sync status for")

        # Sync status for each remittance
        for remittance in filtered_remittances:
            await sync_batch_payment_status(db, org_id, remittance.id)

    except Exception as e:
        logger.error(f"Failed to sync batch payment statuses for org {org_id}: {e}")
