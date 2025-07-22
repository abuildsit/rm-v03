from abc import ABC, abstractmethod
from typing import Any, Dict, List

from prisma import Prisma


class BaseIntegrationDataService(ABC):
    """Handles all data operations for an integration provider."""

    def __init__(self, db: Prisma):
        self.db = db

    @abstractmethod
    async def get_invoices(
        self, org_id: str, filters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Get invoices from provider.

        Args:
            org_id: Organization ID
            filters: Provider-specific filters (status, date_from, date_to, etc.)

        Returns:
            List of invoice dictionaries from the provider
        """
        pass

    @abstractmethod
    async def get_accounts(
        self, org_id: str, filters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Get accounts from provider.

        Args:
            org_id: Organization ID
            filters: Provider-specific filters (type, etc.)

        Returns:
            List of account dictionaries from the provider
        """
        pass

    @abstractmethod
    async def create_payment(
        self, org_id: str, payment_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Post payment to provider.

        Args:
            org_id: Organization ID
            payment_data: Payment details to create

        Returns:
            Created payment details from provider
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
    ) -> Dict[str, Any]:
        """
        Upload attachment to provider.

        Args:
            org_id: Organization ID
            entity_id: ID of the entity to attach to (invoice ID, etc.)
            entity_type: Type of entity (invoice, etc.)
            file_data: File content as bytes
            filename: Name of the file

        Returns:
            Upload result from provider
        """
        pass
