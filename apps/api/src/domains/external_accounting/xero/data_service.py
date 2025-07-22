import asyncio
from datetime import datetime
from typing import List, Optional, cast

import httpx
from prisma.enums import XeroConnectionStatus

from prisma import Prisma
from src.domains.external_accounting.xero.auth.service import XeroService
from src.shared.exceptions import (
    IntegrationConnectionError,
    IntegrationTokenExpiredError,
)

from ..base.data_service import BaseIntegrationDataService
from ..base.types import BaseAccountFilters, BaseInvoiceFilters
from .types import (
    HttpHeaders,
    HttpParams,
    HttpRequestKwargs,
    PaymentData,
    XeroAccount,
    XeroAccountsResponse,
    XeroApiResponse,
    XeroAttachment,
    XeroAttachmentsResponse,
    XeroInvoice,
    XeroInvoicesResponse,
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
        self, org_id: str, filters: BaseInvoiceFilters
    ) -> List[XeroInvoice]:
        """
        Get invoices from Xero API.

        Args:
            org_id: Organization ID
            filters: Filters including status, date_from, date_to, modified_since

        Returns:
            List of typed Xero invoice objects
        """
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

            typed_response = cast(XeroInvoicesResponse, response)
            invoices = typed_response.Invoices
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
        files = {"file": (filename, file_data)}

        response = await self._make_xero_request(
            "POST",
            f"{self.base_url}/{entity_type}/{entity_id}/Attachments/{filename}",
            org_id,
            files=files,
        )

        typed_response = cast(XeroAttachmentsResponse, response)
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
        json: Optional[PaymentData] = None,
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
                    json_data=None,
                    files=None,
                    timeout=30.0,
                )

                if params:
                    request_kwargs.params = params
                if json and not files:
                    request_kwargs.json_data = json
                    request_headers["Content-Type"] = "application/json"
                if files:
                    request_kwargs.files = files

                async with httpx.AsyncClient() as client:
                    # Convert Pydantic model to dict and rename json_data back to json
                    kwargs_dict = request_kwargs.model_dump(exclude_none=True)
                    if "json_data" in kwargs_dict:
                        kwargs_dict["json"] = kwargs_dict.pop("json_data")
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
