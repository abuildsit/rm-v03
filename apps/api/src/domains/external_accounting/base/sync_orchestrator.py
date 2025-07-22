import re
import time
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, List, Optional, cast

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
from .types import (
    BaseAccountFilters,
    BaseInvoiceFilters,
)


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
            filters = (
                BaseAccountFilters(types=account_types, modified_since=None)
                if account_types
                else self._build_account_filters()
            )

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
    ) -> BaseInvoiceFilters:
        """Build filters for invoice sync."""
        filter_data: dict[str, Any] = {"status": ["AUTHORISED", "VOIDED", "DELETED"]}

        # Note: BaseInvoiceFilters doesn't have 'types' field - invoice_types ignored

        if incremental:
            last_sync = await self._get_last_sync_time(org_id, "invoices")
            if last_sync:
                filter_data["modified_since"] = (
                    last_sync.isoformat()
                    if hasattr(last_sync, "isoformat")
                    else str(last_sync)
                )
            else:
                filter_data["date_from"] = (
                    datetime.now() - timedelta(days=months_back * 30)
                ).isoformat()
        else:
            filter_data["date_from"] = (
                datetime.now() - timedelta(days=months_back * 30)
            ).isoformat()

        return BaseInvoiceFilters(**filter_data)

    def _build_account_filters(self) -> BaseAccountFilters:
        """Build filters for account sync."""
        return BaseAccountFilters(types=["BANK"], modified_since=None)

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

    async def _upsert_invoices(self, org_id: str, invoices: List[Any]) -> int:
        """Batch upsert invoices to database."""
        count = 0

        for invoice_data in invoices:
            try:
                await self.db.invoice.upsert(
                    where={
                        "organizationId_invoiceId": {
                            "organizationId": org_id,
                            "invoiceId": invoice_data.InvoiceID,
                        }
                    },
                    data={
                        "create": self._map_invoice_create_data(org_id, invoice_data),
                        "update": self._map_invoice_update_data(invoice_data),
                    },
                )
                count += 1
            except Exception as e:
                print(f"Failed to upsert invoice {invoice_data.get('InvoiceID')}: {e}")
                continue

        return count

    async def _upsert_accounts(self, org_id: str, accounts: List[Any]) -> int:
        """Batch upsert accounts to database."""
        count = 0

        for account_data in accounts:
            try:
                await self.db.bankaccount.upsert(
                    where={
                        "organizationId_xeroAccountId": {
                            "organizationId": org_id,
                            "xeroAccountId": account_data.AccountID,
                        }
                    },
                    data={
                        "create": self._map_account_create_data(org_id, account_data),
                        "update": self._map_account_update_data(account_data),
                    },
                )
                count += 1
            except Exception as e:
                print(f"Failed to upsert account {account_data.AccountID}: {e}")
                continue

        return count

    def _map_invoice_create_data(
        self, org_id: str, invoice_data: Any
    ) -> InvoiceCreateInput:
        """Map provider invoice data to database create format."""
        return {
            "organizationId": org_id,
            "invoiceId": invoice_data.InvoiceID,
            "invoiceNumber": invoice_data.InvoiceNumber,
            "contactName": invoice_data.Contact.Name if invoice_data.Contact else None,
            "contactId": (
                invoice_data.Contact.ContactID if invoice_data.Contact else None
            ),
            "invoiceDate": (
                _parse_xero_date(invoice_data.Date) if invoice_data.Date else None
            ),
            "dueDate": (
                _parse_xero_date(invoice_data.DueDate) if invoice_data.DueDate else None
            ),
            "status": (
                InvoiceStatus(invoice_data.Status.upper())
                if invoice_data.Status
                else None
            ),
            "lineAmountTypes": invoice_data.LineAmountTypes,
            "subTotal": (
                Decimal(str(invoice_data.SubTotal))
                if invoice_data.SubTotal is not None
                else None
            ),
            "totalTax": (
                Decimal(str(invoice_data.TotalTax))
                if invoice_data.TotalTax is not None
                else None
            ),
            "total": (
                Decimal(str(invoice_data.Total))
                if invoice_data.Total is not None
                else None
            ),
            "amountDue": (
                Decimal(str(invoice_data.AmountDue))
                if invoice_data.AmountDue is not None
                else None
            ),
            "amountPaid": (
                Decimal(str(invoice_data.AmountPaid))
                if invoice_data.AmountPaid is not None
                else None
            ),
            "amountCredited": (
                Decimal(str(invoice_data.AmountCredited))
                if invoice_data.AmountCredited is not None
                else None
            ),
            "currencyCode": invoice_data.CurrencyCode or "USD",
            "reference": invoice_data.Reference,
            "brandId": invoice_data.BrandingThemeID,
            "hasErrors": getattr(invoice_data, "HasErrors", False),
            "isDiscounted": getattr(invoice_data, "IsDiscounted", False),
            "hasAttachments": getattr(invoice_data, "HasAttachments", False),
            "sentToContact": getattr(invoice_data, "SentToContact", False),
            "lastSyncedAt": datetime.now(),
            "xeroUpdatedDateUtc": (
                _parse_xero_date(invoice_data.UpdatedDateUTC)
                if invoice_data.UpdatedDateUTC
                else None
            ),
        }

    def _map_invoice_update_data(self, invoice_data: Any) -> InvoiceUpdateInput:
        """Map provider invoice data to database update format."""
        update_data: dict[str, Any] = {
            "lastSyncedAt": datetime.now(),
        }

        if invoice_data.Status:
            update_data["status"] = InvoiceStatus(invoice_data.Status.upper())
        if invoice_data.AmountDue is not None:
            update_data["amountDue"] = Decimal(str(invoice_data.AmountDue))
        if invoice_data.AmountPaid is not None:
            update_data["amountPaid"] = Decimal(str(invoice_data.AmountPaid))
        if invoice_data.AmountCredited is not None:
            update_data["amountCredited"] = Decimal(str(invoice_data.AmountCredited))
        if invoice_data.UpdatedDateUTC:
            parsed_date = _parse_xero_date(invoice_data.UpdatedDateUTC)
            if parsed_date:
                update_data["xeroUpdatedDateUtc"] = parsed_date

        return cast(InvoiceUpdateInput, update_data)

    def _map_account_create_data(
        self, org_id: str, account_data: Any
    ) -> BankAccountCreateInput:
        """Map provider account data to database create format."""
        return {
            "organizationId": org_id,
            "xeroAccountId": account_data.AccountID,
            "xeroName": account_data.Name,
            "xeroCode": account_data.Code,
            "type": account_data.Type or "BANK",
            "status": getattr(account_data, "Status", "ACTIVE"),
            "bankAccountNumber": account_data.BankAccountNumber,
            "currencyCode": account_data.CurrencyCode or "AUD",
            "enablePaymentsToAccount": account_data.EnablePaymentsToAccount or False,
        }

    def _map_account_update_data(self, account_data: Any) -> BankAccountUpdateInput:
        """Map provider account data to database update format."""
        update_data: dict[str, Any] = {}

        if account_data.Name:
            update_data["xeroName"] = account_data.Name
        if hasattr(account_data, "Status") and account_data.Status:
            update_data["status"] = account_data.Status
        if account_data.EnablePaymentsToAccount is not None:
            update_data["enablePaymentsToAccount"] = (
                account_data.EnablePaymentsToAccount
            )

        return cast(BankAccountUpdateInput, update_data)
