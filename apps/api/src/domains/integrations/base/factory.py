from enum import Enum

from prisma.enums import XeroConnectionStatus

from prisma import Prisma
from src.shared.exceptions import IntegrationConnectionError

from .data_service import BaseIntegrationDataService


class IntegrationProvider(str, Enum):
    """Supported integration providers."""

    XERO = "xero"


class IntegrationFactory:
    """Factory for creating integration-specific services."""

    def __init__(self, db: Prisma):
        self.db = db

    async def get_data_service(self, org_id: str) -> BaseIntegrationDataService:
        """Get the data service for an organization's integration."""
        provider = await self._get_organization_provider(org_id)

        if provider == IntegrationProvider.XERO:
            from src.domains.integrations.xero.data_service import XeroDataService

            return XeroDataService(self.db)

        raise IntegrationConnectionError(
            f"Unsupported integration provider: {provider}"
        )

    async def _get_organization_provider(self, org_id: str) -> IntegrationProvider:
        """Determine which integration provider an organization uses."""
        xero_connection = await self.db.xeroconnection.find_first(
            where={
                "organizationId": org_id,
                "connectionStatus": XeroConnectionStatus.connected,
            }
        )

        if xero_connection:
            return IntegrationProvider.XERO

        raise IntegrationConnectionError(
            "No active integration found for this organization"
        )
