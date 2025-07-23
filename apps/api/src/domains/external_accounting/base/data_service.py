from abc import ABC, abstractmethod
from typing import Generic, List, Optional, TypeVar

from prisma import Prisma

from .types import (
    BaseAccountFilters,
    BaseInvoiceFilters,
    BatchPaymentData,
    BatchPaymentResult,
)

# Generic type variables for provider-specific data types
InvoiceType = TypeVar("InvoiceType")
AccountType = TypeVar("AccountType")
PaymentType = TypeVar("PaymentType")
AttachmentType = TypeVar("AttachmentType")
PaymentDataType = TypeVar("PaymentDataType")


class BaseIntegrationDataService(
    ABC, Generic[InvoiceType, AccountType, PaymentType, AttachmentType, PaymentDataType]
):
    """Handles all data operations for an integration provider."""

    def __init__(self, db: Prisma):
        self.db = db

    @abstractmethod
    async def get_invoices(
        self, org_id: str, filters: BaseInvoiceFilters, invoice_id: Optional[str] = None
    ) -> List[InvoiceType]:
        """
        Get invoices from provider.

        Args:
            org_id: Organization ID
            filters: Provider-specific filters (status, date_from, date_to, etc.)
            invoice_id: Optional specific invoice ID to fetch

        Returns:
            List of typed invoice objects from the provider
        """
        pass

    @abstractmethod
    async def get_accounts(
        self, org_id: str, filters: BaseAccountFilters
    ) -> List[AccountType]:
        """
        Get accounts from provider.

        Args:
            org_id: Organization ID
            filters: Provider-specific filters (type, etc.)

        Returns:
            List of typed account objects from the provider
        """
        pass

    @abstractmethod
    async def create_payment(
        self, org_id: str, payment_data: PaymentDataType
    ) -> PaymentType:
        """
        Post payment to provider.

        Args:
            org_id: Organization ID
            payment_data: Payment details to create

        Returns:
            Created payment object from provider
        """
        pass

    @abstractmethod
    async def upload_attachment(
        self,
        org_id: str,
        entity_id: str,
        entity_type: str,
        file_data: bytes,
        filename: str,
    ) -> AttachmentType:
        """
        Upload attachment to provider.

        Args:
            org_id: Organization ID
            entity_id: ID of the entity to attach to (invoice ID, etc.)
            entity_type: Type of entity (invoice, etc.)
            file_data: File content as bytes
            filename: Name of the file

        Returns:
            Uploaded attachment object from provider
        """
        pass

    @abstractmethod
    async def create_batch_payment(
        self, org_id: str, batch_payment_data: BatchPaymentData
    ) -> BatchPaymentResult:
        """
        Create batch payment in provider.

        Args:
            org_id: Organization ID
            batch_payment_data: Batch payment details to create

        Returns:
            Result of batch payment creation with batch_id or error
        """
        pass
