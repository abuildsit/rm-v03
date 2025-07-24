import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Union, cast

import httpx
from prisma.enums import XeroConnectionStatus

from prisma import Prisma
from src.domains.external_accounting.xero.auth.service import XeroService
from src.shared.exceptions import (
    IntegrationConnectionError,
    IntegrationTokenExpiredError,
)

from ..base.data_service import BaseIntegrationDataService
from ..base.types import (
    BaseAccountFilters,
    BaseInvoiceFilters,
    BatchPaymentData,
    BatchPaymentResult,
)
from .types import (
    BatchPaymentStatusResult,
    HttpHeaders,
    HttpParams,
    HttpRequestKwargs,
    PaymentData,
    XeroAccount,
    XeroAccountRef,
    XeroAccountsResponse,
    XeroApiResponse,
    XeroAttachment,
    XeroAttachmentsResponse,
    XeroBankTransactionsResponse,
    XeroBatchPaymentPayment,
    XeroBatchPaymentRequest,
    XeroInvoice,
    XeroInvoiceRef,
    XeroPayment,
    XeroPaymentsResponse,
)


class XeroDataService(
    BaseIntegrationDataService[
        XeroInvoice, XeroAccount, XeroPayment, XeroAttachment, PaymentData
    ]
):
    """Xero-specific API implementation."""

    def __init__(self, db: Prisma):
        super().__init__(db)
        self.base_url = "https://api.xero.com/api.xro/2.0"
        self.xero_service = XeroService(db)

    async def get_invoices(
        self, org_id: str, filters: BaseInvoiceFilters, invoice_id: Optional[str] = None
    ) -> List[XeroInvoice]:
        """
        Get invoices from Xero API.

        Args:
            org_id: Organization ID
            filters: Filters including status, date_from, date_to, modified_since
            invoice_id: Optional specific invoice ID to fetch

        Returns:
            List of typed Xero invoice objects
        """
        # If invoice_id is provided, fetch single invoice
        if invoice_id:
            response = await self._make_xero_request(
                "GET",
                f"{self.base_url}/Invoices/{invoice_id}",
                org_id,
            )
            # Response is a dictionary from JSON, not a Pydantic model
            response_dict = cast(dict, response)
            invoice_dicts = response_dict["Invoices"]
            return [
                XeroInvoice.model_validate(invoice_dict)
                for invoice_dict in invoice_dicts
            ]

        # Bulk invoice fetch logic (existing functionality)
        all_invoices = []
        page = 1

        while True:
            params = HttpParams(page=page, where=None, order=None)

            where_clauses = []
            if filters.status:
                # Build OR conditions for multiple statuses
                status_conditions = [f'Status=="{s}"' for s in filters.status]
                where_clauses.append(f"({' OR '.join(status_conditions)})")

            if filters.date_from:
                # Parse ISO string to datetime for Xero format
                date_from_dt = datetime.fromisoformat(
                    filters.date_from.replace("Z", "+00:00")
                )
                # Xero DateTime format: DateTime(year,month,day)
                y, m, d = date_from_dt.year, date_from_dt.month, date_from_dt.day
                date_str = f"DateTime({y},{m},{d})"
                where_clauses.append(f"Date>={date_str}")

            if filters.date_to:
                # Parse ISO string to datetime for Xero format
                date_to_dt = datetime.fromisoformat(
                    filters.date_to.replace("Z", "+00:00")
                )
                # Xero DateTime format: DateTime(year,month,day)
                date_str = (
                    f"DateTime({date_to_dt.year},"
                    f"{date_to_dt.month},{date_to_dt.day})"
                )
                where_clauses.append(f"Date<={date_str}")

            if where_clauses:
                params.where = " AND ".join(where_clauses)

            headers = {}
            if filters.modified_since:
                # Parse ISO string to datetime for header format
                modified_since_dt = datetime.fromisoformat(
                    filters.modified_since.replace("Z", "+00:00")
                )
                headers["If-Modified-Since"] = modified_since_dt.strftime(
                    "%Y-%m-%dT%H:%M:%S"
                )

            response = await self._make_xero_request(
                "GET",
                f"{self.base_url}/Invoices",
                org_id,
                params=params,
                headers=headers if headers else None,
            )

            # Response is a dictionary from JSON, not a Pydantic model
            response_dict = cast(dict, response)
            invoice_dicts = response_dict["Invoices"]
            invoices = [
                XeroInvoice.model_validate(invoice_dict)
                for invoice_dict in invoice_dicts
            ]
            all_invoices.extend(invoices)

            if len(invoices) < 100:
                break
            page += 1

        return all_invoices

    async def get_accounts(
        self, org_id: str, filters: BaseAccountFilters
    ) -> List[XeroAccount]:
        """
        Get accounts from Xero API.

        Args:
            org_id: Organization ID
            filters: Filters including types

        Returns:
            List of typed Xero account objects (filtered to BANK accounts)
        """
        params = HttpParams(page=None, where=None, order=None)

        where_clauses = ['Type=="BANK"']
        # Note: We only sync BANK type accounts as specified in PRD
        if filters.types:
            # Build OR conditions for multiple types
            type_conditions = [f'Type=="{t}"' for t in filters.types]
            where_clauses = [f"({' OR '.join(type_conditions)})"]

        params.where = " AND ".join(where_clauses)

        response = await self._make_xero_request(
            "GET", f"{self.base_url}/Accounts", org_id, params=params
        )

        typed_response = cast(XeroAccountsResponse, response)
        return typed_response.Accounts

    async def create_payment(
        self, org_id: str, payment_data: PaymentData
    ) -> XeroPayment:
        """
        Create payment in Xero.

        Args:
            org_id: Organization ID
            payment_data: Payment details to create

        Returns:
            Created payment object from Xero
        """
        response = await self._make_xero_request(
            "POST", f"{self.base_url}/Payments", org_id, json=payment_data
        )

        typed_response = cast(XeroPaymentsResponse, response)
        payments = typed_response.Payments
        if not payments:
            raise IntegrationConnectionError("No payment returned from Xero API")
        return payments[0]

    async def upload_attachment(
        self,
        org_id: str,
        entity_id: str,
        entity_type: str,
        file_data: bytes,
        filename: str,
    ) -> XeroAttachment:
        """
        Upload attachment to Xero.

        Args:
            org_id: Organization ID
            entity_id: ID of the entity to attach to
            entity_type: Type of entity (Invoices, etc.)
            file_data: File content as bytes
            filename: Name of the file

        Returns:
            Uploaded attachment object from Xero
        """
        # BankTransactions require raw binary data in body, not form data
        if entity_type == "BankTransactions":
            # Make direct HTTP request with raw data
            access_token = await self.xero_service.get_valid_access_token(org_id)
            connection = await self.db.xeroconnection.find_first(
                where={
                    "organizationId": org_id,
                    "connectionStatus": XeroConnectionStatus.connected,
                }
            )
            if not connection:
                raise IntegrationConnectionError("No active Xero connection found")

            import httpx

            async with httpx.AsyncClient() as client:
                request_headers = {
                    "Authorization": f"Bearer {access_token}",
                    "Xero-Tenant-Id": connection.xeroTenantId,
                    "Content-Type": "application/pdf",
                }

                response = await client.post(
                    f"{self.base_url}/{entity_type}/{entity_id}/Attachments/{filename}",
                    headers=request_headers,
                    content=file_data,
                    timeout=30.0,
                )
                response.raise_for_status()

                # Xero attachment uploads may return empty or non-JSON response
                try:
                    response_data = response.json() if response.content else {}
                except ValueError:
                    # If JSON parsing fails, assume success since HTTP status was OK
                    response_data = {}
        else:
            # Other entity types use form data
            files = {"file": (filename, file_data)}
            response_data = await self._make_xero_request(
                "POST",
                f"{self.base_url}/{entity_type}/{entity_id}/Attachments/{filename}",
                org_id,
                files=files,
            )

        # Handle different response structures for different entity types
        if entity_type == "BankTransactions":
            # BankTransactions attachments may return a different response structure
            # For now, we'll assume success if no error was raised
            from .types import XeroAttachment

            return XeroAttachment(
                AttachmentID="bank-transaction-attachment",
                FileName=filename,
                Url="",
                MimeType="application/pdf",
                ContentLength=len(file_data),
                IncludeOnline=None,
            )
        else:
            # Standard attachment response for other entity types
            typed_response = cast(XeroAttachmentsResponse, response_data)
            attachments = typed_response.Attachments
            if not attachments:
                raise IntegrationConnectionError("No attachment returned from Xero API")
            return attachments[0]

    async def _make_xero_request(
        self,
        method: str,
        url: str,
        org_id: str,
        params: Optional[HttpParams] = None,
        headers: Optional[HttpHeaders] = None,
        json: Optional[
            Union[PaymentData, Dict[str, str | int | float | bool | None]]
        ] = None,
        files: Optional[dict[str, tuple[str, bytes]]] = None,
        max_retries: int = 3,
    ) -> XeroApiResponse:
        """
        Make authenticated request to Xero API with retry logic.

        Args:
            method: HTTP method
            url: Full URL to request
            org_id: Organization ID for token lookup
            params: URL parameters
            json: JSON body
            files: Files to upload
            max_retries: Maximum number of retries

        Returns:
            Typed response from Xero API

        Raises:
            IntegrationConnectionError: For connection failures
            IntegrationTokenExpiredError: For auth failures
        """
        access_token = await self.xero_service.get_valid_access_token(org_id)

        connection = await self.db.xeroconnection.find_first(
            where={
                "organizationId": org_id,
                "connectionStatus": XeroConnectionStatus.connected,
            }
        )
        if not connection:
            raise IntegrationConnectionError("No active Xero connection found")

        tenant_id = connection.xeroTenantId

        for attempt in range(max_retries):
            try:
                request_headers: HttpHeaders = {
                    "Authorization": f"Bearer {access_token}",
                    "Xero-Tenant-Id": tenant_id,
                    "Accept": "application/json",
                }

                # Merge in any additional headers
                if headers:
                    request_headers.update(headers)

                request_kwargs = HttpRequestKwargs(
                    headers=request_headers,
                    params=None,
                    files=None,
                    timeout=30.0,
                )

                if params:
                    request_kwargs.params = params
                if files:
                    request_kwargs.files = files

                async with httpx.AsyncClient() as client:
                    # Convert Pydantic model to dict and add json directly
                    kwargs_dict = request_kwargs.model_dump(exclude_none=True)
                    if json and not files:
                        kwargs_dict["json"] = json
                        request_headers["Content-Type"] = "application/json"
                    response = await client.request(method, url, **kwargs_dict)

                    if response.status_code == 429:
                        retry_after = int(response.headers.get("Retry-After", 60))
                        await asyncio.sleep(retry_after)
                        continue

                    if response.status_code == 401:
                        access_token = await self.xero_service.get_valid_access_token(
                            org_id
                        )
                        request_headers["Authorization"] = f"Bearer {access_token}"
                        continue

                    response.raise_for_status()
                    return cast(XeroApiResponse, response.json())

            except httpx.HTTPStatusError as e:
                if attempt == max_retries - 1:
                    if e.response.status_code == 401:
                        raise IntegrationTokenExpiredError(
                            f"Xero authentication failed: {e.response.text}"
                        )
                    raise IntegrationConnectionError(
                        f"Xero API request failed: {e.response.text}"
                    )

                await asyncio.sleep(2**attempt)

            except httpx.RequestError as e:
                if attempt == max_retries - 1:
                    raise IntegrationConnectionError(
                        f"Xero API request error: {str(e)}"
                    )

                await asyncio.sleep(2**attempt)

        raise IntegrationConnectionError("Max retries exceeded for Xero API request")

    async def create_batch_payment(
        self, org_id: str, batch_payment_data: BatchPaymentData
    ) -> BatchPaymentResult:
        """
        Create batch payment in Xero.

        Args:
            org_id: Organization ID
            batch_payment_data: Batch payment details to create

        Returns:
            Result of batch payment creation with batch_id or error
        """
        try:
            # Convert provider-agnostic data to explicit Xero request model
            xero_request = XeroBatchPaymentRequest(
                Account=XeroAccountRef(AccountID=batch_payment_data.account_id),
                Date=batch_payment_data.payment_date,
                Reference=batch_payment_data.payment_reference,
                Payments=[
                    XeroBatchPaymentPayment(
                        Invoice=XeroInvoiceRef(InvoiceID=payment.invoice_id),
                        Amount=str(payment.amount),
                        Reference=payment.reference,
                    )
                    for payment in batch_payment_data.payments
                ],
            )

            # Make API request with typed request model
            response = await self._make_xero_request(
                "PUT",
                f"{self.base_url}/BatchPayments",
                org_id,
                json=xero_request.model_dump(mode="json"),
            )

            # Parse response
            batch_payments = cast(dict, response).get("BatchPayments", [])

            if not batch_payments:
                raise IntegrationConnectionError(
                    "No batch payment returned from Xero API"
                )

            # Return success result with batch ID
            return BatchPaymentResult(
                success=True,
                batch_id=batch_payments[0]["BatchPaymentID"],
                error_message=None,
            )

        except (IntegrationConnectionError, IntegrationTokenExpiredError):
            # Re-raise integration-specific errors
            raise
        except Exception as e:
            # Convert any other errors to integration errors
            return BatchPaymentResult(
                success=False,
                batch_id=None,
                error_message=f"Batch payment creation failed: {str(e)}",
            )

    async def get_batch_payment_status(
        self, org_id: str, batch_payment_id: str
    ) -> BatchPaymentStatusResult:
        """
        Get batch payment status from Xero using Bank Transactions API.

        Batch payments in Xero are created as bank transactions, so we need to
        query the BankTransactions endpoint to get the current status.

        Args:
            org_id: Organization ID
            batch_payment_id: Xero batch payment ID

        Returns:
            BatchPaymentStatusResult with current status and reconciliation info
        """
        try:
            # Query bank transactions that are part of this batch payment
            # We filter by BatchPayment.BatchPaymentID to find transactions
            where_clause = f'BatchPayment.BatchPaymentID=guid("{batch_payment_id}")'

            params = HttpParams(page=None, where=where_clause, order=None)

            response = await self._make_xero_request(
                "GET",
                f"{self.base_url}/BankTransactions",
                org_id,
                params=params,
            )

            # Parse response as bank transactions
            typed_response = cast(XeroBankTransactionsResponse, response)
            bank_transactions = typed_response.BankTransactions

            if not bank_transactions:
                return BatchPaymentStatusResult(
                    batch_id=batch_payment_id,
                    status="",
                    is_reconciled=False,
                    last_updated="",
                    found=False,
                )

            # Get the first transaction (should all have same status for batch payment)
            first_transaction = bank_transactions[0]

            return BatchPaymentStatusResult(
                batch_id=batch_payment_id,
                status=first_transaction.Status,
                is_reconciled=first_transaction.IsReconciled,
                last_updated=first_transaction.UpdatedDateUTC,
                found=True,
            )

        except Exception:
            # If we can't get status, return not found
            return BatchPaymentStatusResult(
                batch_id=batch_payment_id,
                status="",
                is_reconciled=False,
                last_updated="",
                found=False,
            )
