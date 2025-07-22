# tests/unit/domains/integrations/xero/test_service.py
"""
Tests for XeroService OAuth and token management functionality.
"""
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.domains.integrations.xero.auth.models import (
    XeroAuthUrlResponse,
    XeroCallbackParams,
    XeroConnectionResponse,
    XeroConnectionStatus,
    XeroDisconnectResponse,
    XeroStateTokenPayload,
    XeroTenantInfo,
    XeroTokenResponse,
)
from src.domains.integrations.xero.auth.service import XeroService
from src.shared.exceptions import (
    IntegrationAuthenticationError,
    IntegrationConnectionError,
    IntegrationTenantMismatchError,
    IntegrationTokenExpiredError,
)
from tests.fixtures.xero_fixtures import create_mock_http_response


class TestXeroService:
    """Test suite for XeroService OAuth functionality."""

    @pytest.fixture
    def xero_service(self, mock_prisma: Mock, mock_settings: Mock) -> XeroService:
        """Create XeroService instance with mocked dependencies."""
        with patch(
            "src.domains.integrations.xero.auth.service.settings", mock_settings
        ):
            return XeroService(mock_prisma)

    @pytest.mark.asyncio
    async def test_start_connection_success(
        self,
        xero_service: XeroService,
        mock_prisma: Mock,
        mock_settings: Mock,
    ) -> None:
        """Test successful connection initiation."""
        # Arrange
        org_id = "test-org-id"
        user_id = "test-profile-id"

        # Mock no existing connection
        mock_prisma.xeroconnection.find_first = AsyncMock(return_value=None)

        # Act
        with patch(
            "src.domains.integrations.xero.auth.service.jwt.encode"
        ) as mock_jwt_encode:
            mock_jwt_encode.return_value = "test-jwt-token"
            result = await xero_service.start_connection(org_id, user_id)

        # Assert
        assert isinstance(result, XeroAuthUrlResponse)
        assert result.organization_id == org_id
        assert "https://login.xero.com/identity/connect/authorize" in result.auth_url
        assert "client_id=test-client-id" in result.auth_url
        assert "state=test-jwt-token" in result.auth_url
        assert result.expires_at > datetime.now()

        # Verify database query
        mock_prisma.xeroconnection.find_first.assert_called_once_with(
            where={"organizationId": org_id}
        )

    @pytest.mark.asyncio
    async def test_start_connection_already_connected(
        self,
        xero_service: XeroService,
        mock_prisma: Mock,
        mock_xero_connection: Mock,
    ) -> None:
        """Test connection initiation when already connected."""
        # Arrange
        org_id = "test-org-id"
        user_id = "test-profile-id"

        # Mock existing active connection
        mock_prisma.xeroconnection.find_first = AsyncMock(
            return_value=mock_xero_connection
        )

        # Act & Assert
        with pytest.raises(IntegrationConnectionError) as exc_info:
            await xero_service.start_connection(org_id, user_id)

        assert "already connected to Xero tenant" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_complete_connection_success(
        self,
        xero_service: XeroService,
        mock_prisma: Mock,
        xero_oauth_callback_success_params: dict,
        xero_token_response_data: dict,
        xero_tenant_info_data: dict,
        mock_jwt_state_token_payload: dict,
    ) -> None:
        """Test successful OAuth connection completion."""
        # Arrange
        callback_params = XeroCallbackParams(**xero_oauth_callback_success_params)

        # Mock no existing connection
        mock_prisma.xeroconnection.find_first = AsyncMock(return_value=None)
        mock_prisma.xeroconnection.create = AsyncMock()

        # Act
        with patch.multiple(
            xero_service,
            _validate_state_token=Mock(
                return_value=XeroStateTokenPayload(**mock_jwt_state_token_payload)
            ),
            _exchange_code_for_tokens=AsyncMock(
                return_value=XeroTokenResponse(**xero_token_response_data)
            ),
            _get_tenant_info=AsyncMock(
                return_value=XeroTenantInfo(**xero_tenant_info_data)
            ),
        ):
            result = await xero_service.complete_connection(callback_params)

        # Assert
        assert isinstance(result, XeroConnectionResponse)
        assert result.organization_id == "test-org-id"
        assert result.tenant_name == "Test Organization"
        assert "successfully" in result.message.lower()

        # Verify database operations
        mock_prisma.xeroconnection.create.assert_called_once()
        create_call_args = mock_prisma.xeroconnection.create.call_args[1]["data"]
        assert create_call_args["organizationId"] == "test-org-id"
        assert create_call_args["xeroTenantId"] == "test-tenant-id"

    @pytest.mark.asyncio
    async def test_complete_connection_oauth_error(
        self,
        xero_service: XeroService,
    ) -> None:
        """Test connection completion with OAuth error."""
        # Arrange
        callback_params = XeroCallbackParams(
            error="access_denied", error_description="User denied authorization"
        )

        # Act & Assert
        with pytest.raises(IntegrationAuthenticationError) as exc_info:
            await xero_service.complete_connection(callback_params)

        assert "User denied authorization" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_complete_connection_tenant_mismatch(
        self,
        xero_service: XeroService,
        mock_prisma: Mock,
        mock_xero_connection: Mock,
        xero_oauth_callback_success_params: dict,
        xero_token_response_data: dict,
        mock_jwt_state_token_payload: dict,
    ) -> None:
        """Test connection completion with tenant mismatch."""
        # Arrange
        callback_params = XeroCallbackParams(**xero_oauth_callback_success_params)

        # Mock existing connection with different tenant
        mock_xero_connection.xeroTenantId = "different-tenant-id"
        mock_xero_connection.tenantName = "Different Organization"
        mock_prisma.xeroconnection.find_first = AsyncMock(
            return_value=mock_xero_connection
        )

        # Mock tenant info with different tenant
        different_tenant_info = XeroTenantInfo(
            id="different-connection-uuid",
            tenantId="new-tenant-id",
            tenantName="New Organization",
            tenantType="ORGANISATION",
            createdDateUtc=datetime.now(),
            updatedDateUtc=datetime.now(),
        )

        # Act & Assert
        with patch.multiple(
            xero_service,
            _validate_state_token=Mock(
                return_value=XeroStateTokenPayload(**mock_jwt_state_token_payload)
            ),
            _exchange_code_for_tokens=AsyncMock(
                return_value=XeroTokenResponse(**xero_token_response_data)
            ),
            _get_tenant_info=AsyncMock(return_value=different_tenant_info),
        ):
            with pytest.raises(IntegrationTenantMismatchError) as exc_info:
                await xero_service.complete_connection(callback_params)

        assert "Cannot reconnect to different Xero tenant" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_disconnect_success(
        self,
        xero_service: XeroService,
        mock_prisma: Mock,
        mock_xero_connection: Mock,
    ) -> None:
        """Test successful disconnection."""
        # Arrange
        org_id = "test-org-id"
        mock_prisma.xeroconnection.find_first = AsyncMock(
            return_value=mock_xero_connection
        )
        mock_prisma.xeroconnection.update = AsyncMock()

        # Act
        with patch.multiple(
            xero_service,
            _get_valid_access_token=AsyncMock(return_value="valid-token"),
            _revoke_xero_connection=AsyncMock(),
        ):
            result = await xero_service.disconnect(org_id)

        # Assert
        assert isinstance(result, XeroDisconnectResponse)
        assert result.organization_id == org_id
        assert "successfully" in result.message.lower()

        # Verify database update
        mock_prisma.xeroconnection.update.assert_called_once()
        update_call_args = mock_prisma.xeroconnection.update.call_args[1]["data"]
        assert update_call_args["connectionStatus"] == "revoked"

    @pytest.mark.asyncio
    async def test_disconnect_no_connection(
        self,
        xero_service: XeroService,
        mock_prisma: Mock,
    ) -> None:
        """Test disconnection when no connection exists."""
        # Arrange
        org_id = "test-org-id"
        mock_prisma.xeroconnection.find_first = AsyncMock(return_value=None)

        # Act & Assert
        with pytest.raises(IntegrationConnectionError) as exc_info:
            await xero_service.disconnect(org_id)

        assert "No Xero connection found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_connection_status_connected(
        self,
        xero_service: XeroService,
        mock_prisma: Mock,
        mock_xero_connection: Mock,
    ) -> None:
        """Test getting connection status for active connection."""
        # Arrange
        org_id = "test-org-id"
        mock_prisma.xeroconnection.find_first = AsyncMock(
            return_value=mock_xero_connection
        )

        # Act
        result = await xero_service.get_connection_status(org_id)

        # Assert
        assert isinstance(result, XeroConnectionStatus)
        assert result.connected is True
        assert result.status == "connected"
        assert result.tenant_name == "Test Organization"

    @pytest.mark.asyncio
    async def test_get_connection_status_disconnected(
        self,
        xero_service: XeroService,
        mock_prisma: Mock,
    ) -> None:
        """Test getting connection status when no connection exists."""
        # Arrange
        org_id = "test-org-id"
        mock_prisma.xeroconnection.find_first = AsyncMock(return_value=None)

        # Act
        result = await xero_service.get_connection_status(org_id)

        # Assert
        assert isinstance(result, XeroConnectionStatus)
        assert result.connected is False
        assert result.status == "DISCONNECTED"
        assert result.tenant_name is None

    @pytest.mark.asyncio
    async def test_refresh_access_token_success(
        self,
        xero_service: XeroService,
        mock_prisma: Mock,
        mock_expired_xero_connection: Mock,
        xero_token_response_data: dict,
    ) -> None:
        """Test successful token refresh."""
        # Arrange
        mock_prisma.xeroconnection.update = AsyncMock()

        # Mock HTTP response
        mock_response = create_mock_http_response(xero_token_response_data)

        # Act
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            result = await xero_service._refresh_access_token(
                mock_expired_xero_connection
            )

        # Assert
        assert result == "test-access-token-12345"

        # Verify database update
        mock_prisma.xeroconnection.update.assert_called_once()
        update_call_args = mock_prisma.xeroconnection.update.call_args[1]["data"]
        assert update_call_args["accessToken"] == "test-access-token-12345"
        assert update_call_args["refreshAttempts"] == 1

    @pytest.mark.asyncio
    async def test_refresh_access_token_failure(
        self,
        xero_service: XeroService,
        mock_prisma: Mock,
        mock_expired_xero_connection: Mock,
        xero_error_response_data: dict,
    ) -> None:
        """Test token refresh failure."""
        # Arrange
        mock_prisma.xeroconnection.update = AsyncMock()

        # Mock HTTP error response
        mock_response = create_mock_http_response(xero_error_response_data, 400)

        # Act & Assert
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            with pytest.raises(IntegrationTokenExpiredError):
                await xero_service._refresh_access_token(mock_expired_xero_connection)

        # Verify error was recorded
        mock_prisma.xeroconnection.update.assert_called_once()
        update_call_args = mock_prisma.xeroconnection.update.call_args[1]["data"]
        assert update_call_args["connectionStatus"] == "error"

    @pytest.mark.asyncio
    async def test_exchange_code_for_tokens_success(
        self,
        xero_service: XeroService,
        xero_token_response_data: dict,
    ) -> None:
        """Test successful token exchange."""
        # Arrange
        auth_code = "test-auth-code"
        mock_response = create_mock_http_response(xero_token_response_data)

        # Act
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            result = await xero_service._exchange_code_for_tokens(auth_code)

        # Assert
        assert isinstance(result, XeroTokenResponse)
        assert result.access_token == "test-access-token-12345"
        assert result.refresh_token == "test-refresh-token-12345"

    @pytest.mark.asyncio
    async def test_get_tenant_info_success(
        self,
        xero_service: XeroService,
        xero_connections_response_data: list,
    ) -> None:
        """Test successful tenant info retrieval."""
        # Arrange
        access_token = "test-access-token"
        mock_response = create_mock_http_response(xero_connections_response_data)

        # Act
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await xero_service._get_tenant_info(access_token)

        # Assert
        assert isinstance(result, XeroTenantInfo)
        assert result.tenantId == "test-tenant-id"
        assert result.tenantName == "Test Organization"

    def test_generate_state_token(
        self,
        xero_service: XeroService,
        mock_settings: Mock,
    ) -> None:
        """Test JWT state token generation."""
        # Arrange
        org_id = "test-org-id"
        user_id = "test-profile-id"
        expires_at = datetime.now() + timedelta(minutes=30)

        # Act
        with patch(
            "src.domains.integrations.xero.auth.service.jwt.encode"
        ) as mock_jwt_encode:
            mock_jwt_encode.return_value = "mock-jwt-token"
            result = xero_service._generate_state_token(org_id, user_id, expires_at)

        # Assert
        assert result == "mock-jwt-token"
        mock_jwt_encode.assert_called_once()

        # Verify payload structure
        call_args = mock_jwt_encode.call_args[0][0]
        assert call_args["org_id"] == org_id
        assert call_args["user_id"] == user_id
        assert "csrf_token" in call_args

    def test_validate_state_token_success(
        self,
        xero_service: XeroService,
        mock_jwt_state_token_payload: dict,
    ) -> None:
        """Test successful state token validation."""
        # Arrange
        token = "valid-jwt-token"

        # Act
        with patch(
            "src.domains.integrations.xero.auth.service.jwt.decode"
        ) as mock_jwt_decode:
            mock_jwt_decode.return_value = mock_jwt_state_token_payload
            result = xero_service._validate_state_token(token)

        # Assert
        assert isinstance(result, XeroStateTokenPayload)
        assert result.org_id == "test-org-id"
        assert result.user_id == "test-profile-id"

    def test_validate_state_token_expired(
        self,
        xero_service: XeroService,
    ) -> None:
        """Test state token validation with expired token."""
        # Arrange
        token = "expired-jwt-token"
        expired_payload = {
            "org_id": "test-org-id",
            "user_id": "test-profile-id",
            "csrf_token": "test-csrf-token",
            "issued_at": (datetime.now() - timedelta(hours=1)).isoformat(),
            "expires_at": (
                datetime.now() - timedelta(minutes=30)
            ).isoformat(),  # Expired
        }

        # Act & Assert
        with patch(
            "src.domains.integrations.xero.auth.service.jwt.decode"
        ) as mock_jwt_decode:
            mock_jwt_decode.return_value = expired_payload

            with pytest.raises(IntegrationAuthenticationError) as exc_info:
                xero_service._validate_state_token(token)

            assert "OAuth session expired" in str(exc_info.value)

    def test_is_connection_active_true(
        self,
        xero_service: XeroService,
        mock_xero_connection: Mock,
    ) -> None:
        """Test connection activity check for active connection."""
        # Act
        result = xero_service._is_connection_active(mock_xero_connection)

        # Assert
        assert result is True

    def test_is_connection_active_false_expired(
        self,
        xero_service: XeroService,
        mock_expired_xero_connection: Mock,
    ) -> None:
        """Test connection activity check for expired connection."""
        # Act
        result = xero_service._is_connection_active(mock_expired_xero_connection)

        # Assert
        assert result is False
