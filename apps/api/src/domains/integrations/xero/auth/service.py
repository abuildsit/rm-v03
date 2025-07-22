# apps/api/src/domains/integrations/xero/service.py
import secrets
from datetime import datetime, timedelta

# All required imports are used
from urllib.parse import urlencode

import httpx
import jwt
from prisma.enums import XeroConnectionStatus
from prisma.models import XeroConnection

from prisma import Prisma
from src.core.settings import settings
from src.shared.exceptions import (
    IntegrationAuthenticationError,
    IntegrationConnectionError,
    IntegrationTenantMismatchError,
    IntegrationTokenExpiredError,
)

from .models import (
    XeroAuthUrlResponse,
    XeroCallbackParams,
    XeroConnectionResponse,
)
from .models import XeroConnectionStatus as XeroConnectionStatusModel
from .models import (
    XeroDisconnectResponse,
    XeroStateTokenPayload,
    XeroTenantInfo,
    XeroTokenResponse,
)


class XeroService:
    """Service for managing Xero OAuth connections and token operations."""

    def __init__(self, db: Prisma):
        self.db = db
        self.client_id = settings.XERO_CLIENT_ID
        self.client_secret = settings.XERO_CLIENT_SECRET
        self.redirect_uri = settings.XERO_REDIRECT_URI
        self.scopes = settings.XERO_SCOPES

        # Xero OAuth endpoints
        self.auth_url = "https://login.xero.com/identity/connect/authorize"
        self.token_url = "https://identity.xero.com/connect/token"
        self.connections_url = "https://api.xero.com/connections"

    async def start_connection(self, org_id: str, user_id: str) -> XeroAuthUrlResponse:
        """
        Start the OAuth connection process for an organization.

        Args:
            org_id: Organization ID
            user_id: Profile ID of the user initiating connection

        Returns:
            XeroAuthUrlResponse with authorization URL and expiry

        Raises:
            IntegrationConnectionError: If organization already has active connection
        """
        # Check for existing active connection
        existing_connection = await self.db.xeroconnection.find_first(
            where={"organizationId": org_id}
        )

        if existing_connection and self._is_connection_active(existing_connection):
            raise IntegrationConnectionError(
                f"Organization is already connected to Xero tenant "
                f"'{existing_connection.tenantName}'. "
                "Please disconnect first if you want to reconnect."
            )

        # Generate state token with 30-minute expiry
        expires_at = datetime.now() + timedelta(minutes=30)
        state_token = self._generate_state_token(org_id, user_id, expires_at)

        # Build authorization URL
        auth_params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": self.scopes,
            "state": state_token,
        }

        auth_url = f"{self.auth_url}?{urlencode(auth_params)}"

        return XeroAuthUrlResponse(
            auth_url=auth_url,
            expires_at=expires_at,
            organization_id=org_id,
        )

    async def complete_connection(
        self, callback_params: XeroCallbackParams
    ) -> XeroConnectionResponse:
        """
        Complete the OAuth connection using the callback parameters.

        Args:
            callback_params: Parameters from Xero OAuth callback

        Returns:
            XeroConnectionResponse with connection details

        Raises:
            IntegrationAuthenticationError: For OAuth flow errors
            IntegrationConnectionError: For connection failures
        """
        # Validate callback parameters
        if callback_params.error:
            error_desc = callback_params.error_description or callback_params.error
            raise IntegrationAuthenticationError(
                f"OAuth authorization failed: {error_desc}"
            )

        if not callback_params.code or not callback_params.state:
            raise IntegrationAuthenticationError("Missing required OAuth parameters")

        # Validate and decode state token
        state_payload = self._validate_state_token(callback_params.state)
        org_id = state_payload.org_id

        # Exchange authorization code for tokens
        token_response = await self._exchange_code_for_tokens(callback_params.code)

        # Get tenant information
        tenant_info = await self._get_tenant_info(token_response.access_token)

        # Check for tenant mismatch on reconnection
        existing_connection = await self.db.xeroconnection.find_first(
            where={"organizationId": org_id}
        )

        if (
            existing_connection
            and existing_connection.xeroTenantId != tenant_info.tenantId
        ):
            raise IntegrationTenantMismatchError(
                f"Cannot reconnect to different Xero tenant. "
                f"Previously connected to '{existing_connection.tenantName}', "
                f"attempting to connect to '{tenant_info.tenantName}'"
            )

        # Store/update connection
        expires_at = datetime.now() + timedelta(seconds=token_response.expires_in)

        if existing_connection:
            await self.db.xeroconnection.update(
                where={"id": existing_connection.id},
                data={
                    "xeroTenantId": tenant_info.tenantId,
                    "tenantName": tenant_info.tenantName,
                    "tenantType": tenant_info.tenantType,
                    "accessToken": token_response.access_token,
                    "refreshToken": token_response.refresh_token,
                    "expiresAt": expires_at,
                    "connectionStatus": XeroConnectionStatus.connected,
                    "lastError": None,
                    "lastRefreshedAt": datetime.now(),
                    "refreshAttempts": 0,
                    "updatedAt": datetime.now(),
                },
            )
        else:
            await self.db.xeroconnection.create(
                data={
                    "organizationId": org_id,
                    "xeroTenantId": tenant_info.tenantId,
                    "tenantName": tenant_info.tenantName,
                    "tenantType": tenant_info.tenantType,
                    "accessToken": token_response.access_token,
                    "refreshToken": token_response.refresh_token,
                    "expiresAt": expires_at,
                    "connectionStatus": XeroConnectionStatus.connected,
                    "lastError": None,
                    "lastRefreshedAt": datetime.now(),
                    "refreshAttempts": 0,
                    "updatedAt": datetime.now(),
                }
            )

        return XeroConnectionResponse(
            message="Xero connection established successfully",
            connected_at=datetime.now(),
            tenant_name=tenant_info.tenantName,
            organization_id=org_id,
        )

    async def disconnect(self, org_id: str) -> XeroDisconnectResponse:
        """
        Disconnect Xero integration for an organization.

        Args:
            org_id: Organization ID

        Returns:
            XeroDisconnectResponse with disconnection details

        Raises:
            IntegrationConnectionError: If no connection exists
        """
        connection = await self.db.xeroconnection.find_first(
            where={"organizationId": org_id}
        )

        if not connection:
            raise IntegrationConnectionError(
                "No Xero connection found for this organization"
            )

        # Attempt to revoke connection in Xero (best effort)
        try:
            if self._is_connection_active(connection):
                access_token = await self._get_valid_access_token(connection)
                await self._revoke_xero_connection(
                    access_token, connection.xeroTenantId
                )
        except Exception as e:
            # Log error but don't fail disconnection
            print(f"Failed to revoke Xero connection: {e}")

        # Update connection status to revoked
        disconnected_at = datetime.now()
        await self.db.xeroconnection.update(
            where={"id": connection.id},
            data={
                "connectionStatus": XeroConnectionStatus.revoked,
                "updatedAt": disconnected_at,
            },
        )

        return XeroDisconnectResponse(
            message="Xero connection disconnected successfully",
            disconnected_at=disconnected_at,
            organization_id=org_id,
        )

    async def get_connection_status(self, org_id: str) -> XeroConnectionStatusModel:
        """
        Get the current connection status for an organization.

        Args:
            org_id: Organization ID

        Returns:
            XeroConnectionStatus with current connection details
        """
        connection = await self.db.xeroconnection.find_first(
            where={"organizationId": org_id}
        )

        return XeroConnectionStatusModel.from_prisma(connection)

    async def get_valid_access_token(self, org_id: str) -> str:
        """
        Get a valid access token for the organization, refreshing if necessary.

        Args:
            org_id: Organization ID

        Returns:
            Valid access token

        Raises:
            IntegrationConnectionError: If no connection exists
            IntegrationTokenExpiredError: If token refresh fails
        """
        connection = await self.db.xeroconnection.find_first(
            where={"organizationId": org_id}
        )

        if not connection:
            raise IntegrationConnectionError(
                "No Xero connection found for this organization"
            )

        return await self._get_valid_access_token(connection)

    def _generate_state_token(
        self, org_id: str, user_id: str, expires_at: datetime
    ) -> str:
        """Generate JWT state token for OAuth flow."""
        if not settings.jwt_secret:
            raise IntegrationAuthenticationError("JWT secret not configured")

        payload = XeroStateTokenPayload(
            org_id=org_id,
            user_id=user_id,
            csrf_token=secrets.token_urlsafe(32),
            issued_at=datetime.now(),
            expires_at=expires_at,
        )

        return jwt.encode(
            payload.model_dump(mode="json"),
            settings.jwt_secret,
            algorithm="HS256",
        )

    def _validate_state_token(self, token: str) -> XeroStateTokenPayload:
        """Validate and decode JWT state token."""
        if not settings.jwt_secret:
            raise IntegrationAuthenticationError("JWT secret not configured")

        try:
            payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
            state_payload = XeroStateTokenPayload(**payload)

            # Check expiry
            if datetime.now() > state_payload.expires_at:
                raise IntegrationAuthenticationError("OAuth session expired")

            return state_payload
        except jwt.InvalidTokenError as e:
            raise IntegrationAuthenticationError(f"Invalid OAuth state token: {e}")

    async def _exchange_code_for_tokens(self, code: str) -> XeroTokenResponse:
        """Exchange OAuth authorization code for access tokens."""
        token_data = {
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "redirect_uri": self.redirect_uri,
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self.token_url,
                    data=token_data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                response.raise_for_status()
                token_json = response.json()

                return XeroTokenResponse(**token_json)
            except httpx.HTTPStatusError as e:
                raise IntegrationAuthenticationError(
                    f"Token exchange failed: {e.response.text}"
                )
            except httpx.RequestError as e:
                raise IntegrationConnectionError(f"Token exchange request failed: {e}")

    async def _get_tenant_info(self, access_token: str) -> XeroTenantInfo:
        """Get tenant information from Xero connections endpoint."""
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(self.connections_url, headers=headers)
                response.raise_for_status()
                connections = response.json()

                if not connections:
                    raise IntegrationConnectionError(
                        "No Xero tenant found for this connection"
                    )

                # Use the first connection (should only be one for new connections)
                tenant_data = connections[0]
                return XeroTenantInfo(**tenant_data)
            except httpx.HTTPStatusError as e:
                raise IntegrationConnectionError(
                    f"Failed to get tenant info: {e.response.text}"
                )
            except httpx.RequestError as e:
                raise IntegrationConnectionError(f"Tenant info request failed: {e}")

    async def _get_valid_access_token(self, connection: XeroConnection) -> str:
        """Get valid access token, refreshing if necessary."""
        # Check if token needs refresh
        if datetime.now() >= connection.expiresAt:
            return await self._refresh_access_token(connection)

        return connection.accessToken

    async def _refresh_access_token(self, connection: XeroConnection) -> str:
        """Refresh expired access token."""
        refresh_data = {
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": connection.refreshToken,
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self.token_url,
                    data=refresh_data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                response.raise_for_status()
                token_json = response.json()
                token_response = XeroTokenResponse(**token_json)

                # Update stored tokens
                expires_at = datetime.now() + timedelta(
                    seconds=token_response.expires_in
                )
                await self.db.xeroconnection.update(
                    where={"id": connection.id},
                    data={
                        "accessToken": token_response.access_token,
                        "refreshToken": token_response.refresh_token,
                        "expiresAt": expires_at,
                        "lastRefreshedAt": datetime.now(),
                        "refreshAttempts": (connection.refreshAttempts or 0) + 1,
                        "lastError": None,
                    },
                )

                return token_response.access_token
            except httpx.HTTPStatusError as e:
                error_msg = f"Token refresh failed: {e.response.text}"

                # Update connection with error
                await self.db.xeroconnection.update(
                    where={"id": connection.id},
                    data={
                        "connectionStatus": XeroConnectionStatus.error,
                        "lastError": error_msg,
                        "refreshAttempts": (connection.refreshAttempts or 0) + 1,
                    },
                )

                raise IntegrationTokenExpiredError(error_msg)
            except httpx.RequestError as e:
                error_msg = f"Token refresh request failed: {e}"

                await self.db.xeroconnection.update(
                    where={"id": connection.id},
                    data={
                        "lastError": error_msg,
                        "refreshAttempts": (connection.refreshAttempts or 0) + 1,
                    },
                )

                raise IntegrationConnectionError(error_msg)

    async def _revoke_xero_connection(self, access_token: str, tenant_id: str) -> None:
        """Revoke connection in Xero."""
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        # Get connection ID from Xero
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(self.connections_url, headers=headers)
                response.raise_for_status()
                connections = response.json()

                # Find connection with matching tenant ID
                connection_id = None
                for conn in connections:
                    if conn.get("tenantId") == tenant_id:
                        connection_id = conn.get("id")
                        break

                if connection_id:
                    # Delete the connection
                    await client.delete(
                        f"{self.connections_url}/{connection_id}", headers=headers
                    )
            except Exception as e:
                # Log error but don't raise - disconnection should still succeed
                print(f"Failed to revoke Xero connection: {e}")

    def _is_connection_active(self, connection: XeroConnection) -> bool:
        """Check if a connection is currently active."""
        return (
            connection.connectionStatus == XeroConnectionStatus.connected
            and connection.expiresAt > datetime.now()
        )
