import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional, cast

import httpx
from prisma.enums import XeroConnectionStatus

from prisma import Prisma
from src.domains.external_accounting.xero.auth.service import XeroService
from src.shared.exceptions import (
    IntegrationConnectionError,
    IntegrationTokenExpiredError,
)

from ..base.data_service import BaseIntegrationDataService


class XeroDataService(BaseIntegrationDataService):
    """Xero-specific API implementation."""

    def __init__(self, db: Prisma):
        super().__init__(db)
        self.base_url = "https://api.xero.com/api.xro/2.0"
        self.xero_service = XeroService(db)

    async def get_invoices(
        self, org_id: str, filters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Get invoices from Xero API.

        Args:
            org_id: Organization ID
            filters: Filters including status, date_from, date_to, modified_since

        Returns:
            List of invoice dictionaries from Xero
        """
        all_invoices = []
        page = 1

        while True:
            params: Dict[str, Any] = {"page": page}

            where_clauses = []
            if filters.get("status"):
                # Build OR conditions for multiple statuses
                status_conditions = [f'Status=="{s}"' for s in filters["status"]]
                where_clauses.append(f"({' OR '.join(status_conditions)})")

            if filters.get("date_from"):
                date_from_dt = cast(datetime, filters["date_from"])
                # Xero DateTime format: DateTime(year,month,day)
                y, m, d = date_from_dt.year, date_from_dt.month, date_from_dt.day
                date_str = f"DateTime({y},{m},{d})"
                where_clauses.append(f"Date>={date_str}")

            if filters.get("date_to"):
                date_to_dt = cast(datetime, filters["date_to"])
                # Xero DateTime format: DateTime(year,month,day)
                date_str = (
                    f"DateTime({date_to_dt.year},{date_to_dt.month},{date_to_dt.day})"
                )
                where_clauses.append(f"Date<={date_str}")

            if where_clauses:
                params["where"] = " AND ".join(where_clauses)

            if filters.get("modified_since"):
                modified_since_dt = cast(datetime, filters["modified_since"])
                params["If-Modified-Since"] = modified_since_dt.strftime(
                    "%Y-%m-%dT%H:%M:%S"
                )

            response = await self._make_xero_request(
                "GET", f"{self.base_url}/Invoices", org_id, params=params
            )

            invoices = response.get("Invoices", [])
            all_invoices.extend(invoices)

            if len(invoices) < 100:
                break
            page += 1

        return all_invoices

    async def get_accounts(
        self, org_id: str, filters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Get accounts from Xero API.

        Args:
            org_id: Organization ID
            filters: Filters including types

        Returns:
            List of account dictionaries from Xero (filtered to BANK accounts)
        """
        params: Dict[str, Any] = {}

        where_clauses = ['Type=="BANK"']
        # Note: We only sync BANK type accounts as specified in PRD
        if filters.get("types"):
            # Build OR conditions for multiple types
            type_conditions = [f'Type=="{t}"' for t in filters["types"]]
            where_clauses = [f"({' OR '.join(type_conditions)})"]

        params["where"] = " AND ".join(where_clauses)

        response = await self._make_xero_request(
            "GET", f"{self.base_url}/Accounts", org_id, params=params
        )

        return cast(List[Dict[str, Any]], response.get("Accounts", []))

    async def create_payment(
        self, org_id: str, payment_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create payment in Xero.

        Args:
            org_id: Organization ID
            payment_data: Payment details to create

        Returns:
            Created payment details from Xero
        """
        response = await self._make_xero_request(
            "POST", f"{self.base_url}/Payments", org_id, json=payment_data
        )

        payments = response.get("Payments", [{}])
        return cast(Dict[str, Any], payments[0] if payments else {})

    async def upload_attachment(
        self,
        org_id: str,
        entity_id: str,
        entity_type: str,
        file_data: bytes,
        filename: str,
    ) -> Dict[str, Any]:
        """
        Upload attachment to Xero.

        Args:
            org_id: Organization ID
            entity_id: ID of the entity to attach to
            entity_type: Type of entity (Invoices, etc.)
            file_data: File content as bytes
            filename: Name of the file

        Returns:
            Upload result from Xero
        """
        files = {"file": (filename, file_data)}

        response = await self._make_xero_request(
            "POST",
            f"{self.base_url}/{entity_type}/{entity_id}/Attachments/{filename}",
            org_id,
            files=files,
        )

        attachments = response.get("Attachments", [{}])
        return cast(Dict[str, Any], attachments[0] if attachments else {})

    async def _make_xero_request(
        self,
        method: str,
        url: str,
        org_id: str,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        files: Optional[Dict[str, Any]] = None,
        max_retries: int = 3,
    ) -> Dict[str, Any]:
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
            JSON response from Xero

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
                headers = {
                    "Authorization": f"Bearer {access_token}",
                    "Xero-Tenant-Id": tenant_id,
                    "Accept": "application/json",
                }

                request_kwargs: Dict[str, Any] = {
                    "headers": headers,
                    "timeout": 30.0,
                }

                if params:
                    request_kwargs["params"] = params
                if json and not files:
                    request_kwargs["json"] = json
                    headers["Content-Type"] = "application/json"
                if files:
                    request_kwargs["files"] = files

                async with httpx.AsyncClient() as client:
                    response = await client.request(method, url, **request_kwargs)

                    if response.status_code == 429:
                        retry_after = int(response.headers.get("Retry-After", 60))
                        await asyncio.sleep(retry_after)
                        continue

                    if response.status_code == 401:
                        access_token = await self.xero_service.get_valid_access_token(
                            org_id
                        )
                        headers["Authorization"] = f"Bearer {access_token}"
                        continue

                    response.raise_for_status()
                    return cast(Dict[str, Any], response.json())

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
