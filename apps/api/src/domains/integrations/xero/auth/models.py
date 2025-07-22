# apps/api/src/domains/integrations/xero/models.py
from datetime import datetime, timezone
from typing import Optional

from prisma.enums import XeroConnectionStatus as PrismaXeroConnectionStatus
from prisma.models import XeroConnection
from pydantic import BaseModel, Field


class XeroAuthUrlResponse(BaseModel):
    """Response model for OAuth authorization URL generation."""

    auth_url: str = Field(..., description="Xero OAuth authorization URL")
    expires_at: datetime = Field(..., description="When the state token expires")
    organization_id: str = Field(..., description="Organization ID")


class XeroConnectionStatus(BaseModel):
    """Response model for Xero connection status."""

    connected: bool = Field(
        ..., description="Whether organization is connected to Xero"
    )
    status: str = Field(..., description="Connection status")
    tenant_id: Optional[str] = Field(None, description="Xero tenant ID if connected")
    tenant_name: Optional[str] = Field(
        None, description="Xero tenant name if connected"
    )
    expires_at: Optional[datetime] = Field(
        None, description="When the access token expires"
    )
    last_refreshed_at: Optional[datetime] = Field(
        None, description="Last token refresh time"
    )
    connected_at: Optional[datetime] = Field(
        None, description="When connection was established"
    )
    last_error: Optional[str] = Field(None, description="Last error message if any")
    refresh_attempts: Optional[int] = Field(
        None, description="Number of refresh attempts"
    )

    @classmethod
    def from_prisma(
        cls, connection: Optional[XeroConnection]
    ) -> "XeroConnectionStatus":
        """Create status response from Prisma XeroConnection model."""
        if not connection:
            return cls(
                connected=False,
                status="DISCONNECTED",
                tenant_id=None,
                tenant_name=None,
                expires_at=None,
                last_refreshed_at=None,
                connected_at=None,
                last_error=None,
                refresh_attempts=None,
            )

        is_connected = (
            connection.connectionStatus == PrismaXeroConnectionStatus.connected
            and connection.expiresAt > datetime.now(timezone.utc)
        )

        return cls(
            connected=is_connected,
            status=connection.connectionStatus.value,
            tenant_id=connection.xeroTenantId,
            tenant_name=connection.tenantName,
            expires_at=connection.expiresAt,
            last_refreshed_at=connection.lastRefreshedAt,
            connected_at=connection.createdAt,
            last_error=connection.lastError,
            refresh_attempts=connection.refreshAttempts,
        )


class XeroCallbackParams(BaseModel):
    """Query parameters from Xero OAuth callback."""

    code: Optional[str] = Field(None, description="OAuth authorization code")
    state: Optional[str] = Field(None, description="JWT state token")
    error: Optional[str] = Field(None, description="Error code if authorization failed")
    error_description: Optional[str] = Field(None, description="Error description")


class XeroTokenResponse(BaseModel):
    """Response from Xero token endpoint."""

    access_token: str = Field(..., description="Access token for API calls")
    refresh_token: str = Field(..., description="Refresh token for token renewal")
    expires_in: int = Field(..., description="Token lifetime in seconds")
    token_type: str = Field(default="Bearer", description="Token type")
    scope: Optional[str] = Field(None, description="Granted scopes")


class XeroTenantInfo(BaseModel):
    """Information about a Xero tenant from connections endpoint."""

    id: str = Field(..., description="Xero tenant UUID")
    tenantId: str = Field(..., description="Xero tenant ID")
    tenantName: str = Field(..., description="Organization name in Xero")
    tenantType: str = Field(..., description="Tenant type (ORGANISATION, PRACTICE)")
    createdDateUtc: datetime = Field(..., description="When tenant was created")
    updatedDateUtc: datetime = Field(..., description="When tenant was last updated")


class XeroDisconnectResponse(BaseModel):
    """Response model for disconnection."""

    message: str = Field(..., description="Success message")
    disconnected_at: datetime = Field(..., description="When disconnection occurred")
    organization_id: str = Field(..., description="Organization ID")


class XeroStateTokenPayload(BaseModel):
    """JWT payload for OAuth state token."""

    org_id: str = Field(..., description="Organization ID")
    user_id: str = Field(..., description="User profile ID")
    csrf_token: str = Field(..., description="CSRF protection token")
    issued_at: datetime = Field(..., description="Token issue time")
    expires_at: datetime = Field(..., description="Token expiry time")


class XeroErrorResponse(BaseModel):
    """Standard error response format for Xero-related errors."""

    detail: str = Field(..., description="Error message")
    error_code: Optional[str] = Field(None, description="Xero-specific error code")
    timestamp: datetime = Field(
        default_factory=datetime.now, description="Error timestamp"
    )


class XeroConnectionResponse(BaseModel):
    """Response model for successful connection."""

    message: str = Field(..., description="Success message")
    connected_at: datetime = Field(..., description="When connection was established")
    tenant_name: str = Field(..., description="Connected Xero organization name")
    organization_id: str = Field(..., description="Organization ID")
