import re
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, cast

from prisma.enums import InvoiceStatus
from prisma.types import (
    BankAccountCreateInput,
    BankAccountUpdateInput,
    InvoiceCreateInput,
    InvoiceUpdateInput,
)

from prisma import Prisma

from .data_service import BaseIntegrationDataService
from .models import SyncResult


def _parse_xero_date(date_str: str) -> Optional[datetime]:
    """
    Parse Xero API date format.

    Xero returns dates in format '/Date(1748476800000+0000)/' where the number
    is milliseconds since Unix epoch.

    Args:
        date_str: Date string from Xero API

    Returns:
        Parsed datetime object or None if parsing fails
    """
    if not date_str:
        return None

    # Handle both /Date()/ format and ISO format
    if date_str.startswith("/Date("):
        # Extract timestamp from /Date(1748476800000+0000)/
        match = re.match(r"/Date\((\d+)([+-]\d{4})?\)/", date_str)
        if match:
            timestamp_ms = int(match.group(1))
            # Convert milliseconds to seconds for Python datetime
            timestamp_s = timestamp_ms / 1000
            return datetime.fromtimestamp(timestamp_s, tz=None).replace(tzinfo=None)
    else:
        # Handle ISO format dates (fallback)
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except ValueError:
            pass

    return None


class SyncOrchestrator:
    """Generic sync logic that works with any provider."""

    def __init__(self, db: Prisma):
        self.db = db

    async def sync_invoices(
        self,
        data_service: BaseIntegrationDataService,
        org_id: str,
        incremental: bool = True,
        invoice_types: Optional[List[str]] = None,
        months_back: int = 12,
    ) -> SyncResult:
        """
        Sync invoices from the accounting system.

        Args:
            data_service: Provider-specific data service
            org_id: Organization ID
            incremental: If True, only sync invoices modified since last sync
            invoice_types: Optional list of invoice types to sync
            months_back: Number of months back to sync (if not incremental)

        Returns:
            SyncResult with sync metrics and status
        """
        start_time = time.time()

        try:
            filters = await self._build_invoice_filters(
                org_id, incremental, invoice_types, months_back
            )

            invoices = await data_service.get_invoices(org_id, filters)

            count = await self._upsert_invoices(org_id, invoices)

            duration = time.time() - start_time

            return SyncResult(
                object_type="invoices",
                success=True,
                count=count,
                duration_seconds=duration,
                last_modified=datetime.now(),
            )

        except Exception as e:
            duration = time.time() - start_time
            return SyncResult(
                object_type="invoices",
                success=False,
                count=0,
                duration_seconds=duration,
                error=str(e),
            )

    async def sync_accounts(
        self,
        data_service: BaseIntegrationDataService,
        org_id: str,
        account_types: Optional[List[str]] = None,
    ) -> SyncResult:
        """
        Sync accounts from the accounting system.

        Args:
            data_service: Provider-specific data service
            org_id: Organization ID
            account_types: Optional list of account types to sync

        Returns:
            SyncResult with sync metrics and status
        """
        start_time = time.time()

        try:
            filters = {"types": account_types} if account_types else {}

            accounts = await data_service.get_accounts(org_id, filters)

            count = await self._upsert_accounts(org_id, accounts)

            duration = time.time() - start_time

            return SyncResult(
                object_type="accounts",
                success=True,
                count=count,
                duration_seconds=duration,
                last_modified=datetime.now(),
            )

        except Exception as e:
            duration = time.time() - start_time
            return SyncResult(
                object_type="accounts",
                success=False,
                count=0,
                duration_seconds=duration,
                error=str(e),
            )

    async def _build_invoice_filters(
        self,
        org_id: str,
        incremental: bool,
        invoice_types: Optional[List[str]],
        months_back: int,
    ) -> Dict[str, Any]:
        """Build filters for invoice sync."""
        filters: Dict[str, Any] = {"status": ["AUTHORISED", "VOIDED", "DELETED"]}

        if invoice_types:
            filters["types"] = invoice_types

        if incremental:
            last_sync = await self._get_last_sync_time(org_id, "invoices")
            if last_sync:
                filters["modified_since"] = last_sync
            else:
                filters["date_from"] = datetime.now() - timedelta(days=months_back * 30)
        else:
            filters["date_from"] = datetime.now() - timedelta(days=months_back * 30)

        return filters

    async def _get_last_sync_time(
        self, org_id: str, object_type: str
    ) -> Optional[datetime]:
        """Get the last successful sync time for an organization and object type."""
        last_sync = (
            await self.db.invoice.find_first(
                where={"organizationId": org_id},
                order={"lastSyncedAt": "desc"},
            )
            if object_type == "invoices"
            else await self.db.bankaccount.find_first(
                where={"organizationId": org_id},
                order={"updatedAt": "desc"},
            )
        )

        return (
            last_sync.lastSyncedAt
            if last_sync and hasattr(last_sync, "lastSyncedAt")
            else None
        )

    async def _upsert_invoices(
        self, org_id: str, invoices: List[Dict[str, Any]]
    ) -> int:
        """Batch upsert invoices to database."""
        count = 0

        for invoice_data in invoices:
            try:
                await self.db.invoice.upsert(
                    where={
                        "organizationId_invoiceId": {
                            "organizationId": org_id,
                            "invoiceId": invoice_data["InvoiceID"],
                        }
                    },
                    data={
                        "create": cast(
                            InvoiceCreateInput,
                            self._map_invoice_create_data(org_id, invoice_data),
                        ),
                        "update": cast(
                            InvoiceUpdateInput,
                            self._map_invoice_update_data(invoice_data),
                        ),
                    },
                )
                count += 1
            except Exception as e:
                print(f"Failed to upsert invoice {invoice_data.get('InvoiceID')}: {e}")
                continue

        return count

    async def _upsert_accounts(
        self, org_id: str, accounts: List[Dict[str, Any]]
    ) -> int:
        """Batch upsert accounts to database."""
        count = 0

        for account_data in accounts:
            try:
                await self.db.bankaccount.upsert(
                    where={
                        "organizationId_xeroAccountId": {
                            "organizationId": org_id,
                            "xeroAccountId": account_data["AccountID"],
                        }
                    },
                    data={
                        "create": cast(
                            BankAccountCreateInput,
                            self._map_account_create_data(org_id, account_data),
                        ),
                        "update": cast(
                            BankAccountUpdateInput,
                            self._map_account_update_data(account_data),
                        ),
                    },
                )
                count += 1
            except Exception as e:
                print(f"Failed to upsert account {account_data.get('AccountID')}: {e}")
                continue

        return count

    def _map_invoice_create_data(
        self, org_id: str, invoice_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Map provider invoice data to database create format."""
        return {
            "organizationId": org_id,
            "invoiceId": invoice_data["InvoiceID"],
            "invoiceNumber": invoice_data.get("InvoiceNumber"),
            "contactName": invoice_data.get("Contact", {}).get("Name"),
            "contactId": invoice_data.get("Contact", {}).get("ContactID"),
            "invoiceDate": (
                _parse_xero_date(invoice_data["Date"])
                if invoice_data.get("Date")
                else None
            ),
            "dueDate": (
                _parse_xero_date(invoice_data["DueDate"])
                if invoice_data.get("DueDate")
                else None
            ),
            "status": (
                InvoiceStatus(invoice_data["Status"].upper())
                if invoice_data.get("Status")
                else None
            ),
            "lineAmountTypes": invoice_data.get("LineAmountTypes"),
            "subTotal": (
                float(invoice_data["SubTotal"])
                if invoice_data.get("SubTotal")
                else None
            ),
            "totalTax": (
                float(invoice_data["TotalTax"])
                if invoice_data.get("TotalTax")
                else None
            ),
            "total": (
                float(invoice_data["Total"]) if invoice_data.get("Total") else None
            ),
            "amountDue": (
                float(invoice_data["AmountDue"])
                if invoice_data.get("AmountDue")
                else None
            ),
            "amountPaid": (
                float(invoice_data["AmountPaid"])
                if invoice_data.get("AmountPaid")
                else None
            ),
            "amountCredited": (
                float(invoice_data["AmountCredited"])
                if invoice_data.get("AmountCredited")
                else None
            ),
            "currencyCode": invoice_data.get("CurrencyCode", "USD"),
            "reference": invoice_data.get("Reference"),
            "brandId": invoice_data.get("BrandingThemeID"),
            "hasErrors": invoice_data.get("HasErrors", False),
            "isDiscounted": invoice_data.get("IsDiscounted", False),
            "hasAttachments": invoice_data.get("HasAttachments", False),
            "sentToContact": invoice_data.get("SentToContact", False),
            "lastSyncedAt": datetime.now(),
            "xeroUpdatedDateUtc": (
                _parse_xero_date(invoice_data["UpdatedDateUTC"])
                if invoice_data.get("UpdatedDateUTC")
                else None
            ),
        }

    def _map_invoice_update_data(self, invoice_data: Dict[str, Any]) -> Dict[str, Any]:
        """Map provider invoice data to database update format."""
        update_data: Dict[str, Any] = {
            "lastSyncedAt": datetime.now(),
        }

        if invoice_data.get("Status"):
            update_data["status"] = InvoiceStatus(invoice_data["Status"].upper())
        if invoice_data.get("AmountDue"):
            update_data["amountDue"] = float(invoice_data["AmountDue"])
        if invoice_data.get("AmountPaid"):
            update_data["amountPaid"] = float(invoice_data["AmountPaid"])
        if invoice_data.get("AmountCredited"):
            update_data["amountCredited"] = float(invoice_data["AmountCredited"])
        if invoice_data.get("UpdatedDateUTC"):
            parsed_date = _parse_xero_date(invoice_data["UpdatedDateUTC"])
            if parsed_date:
                update_data["xeroUpdatedDateUtc"] = parsed_date

        return update_data

    def _map_account_create_data(
        self, org_id: str, account_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Map provider account data to database create format."""
        return {
            "organizationId": org_id,
            "xeroAccountId": account_data["AccountID"],
            "xeroName": account_data.get("Name"),
            "xeroCode": account_data.get("Code"),
            "type": account_data.get("Type", "BANK"),
            "status": account_data.get("Status", "ACTIVE"),
            "bankAccountNumber": account_data.get("BankAccountNumber"),
            "currencyCode": account_data.get("CurrencyCode", "AUD"),
            "enablePaymentsToAccount": account_data.get(
                "EnablePaymentsToAccount", False
            ),
        }

    def _map_account_update_data(self, account_data: Dict[str, Any]) -> Dict[str, Any]:
        """Map provider account data to database update format."""
        update_data: Dict[str, Any] = {}

        if account_data.get("Name"):
            update_data["xeroName"] = account_data["Name"]
        if account_data.get("Status"):
            update_data["status"] = account_data["Status"]
        if account_data.get("EnablePaymentsToAccount") is not None:
            update_data["enablePaymentsToAccount"] = account_data[
                "EnablePaymentsToAccount"
            ]

        return update_data
