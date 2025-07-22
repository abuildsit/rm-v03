# tests/unit/domains/integrations/xero/test_models.py
"""
Tests for Xero integration Pydantic models.
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest
from prisma.enums import XeroConnectionStatus
from prisma.models import XeroConnection
from pydantic import ValidationError

from src.domains.integrations.xero.auth.models import (
    XeroAuthUrlResponse,
    XeroCallbackParams,
    XeroConnectionResponse,
)
from src.domains.integrations.xero.auth.models import (
    XeroConnectionStatus as XeroConnectionStatusModel,
)
from src.domains.integrations.xero.auth.models import (
    XeroDisconnectResponse,
    XeroErrorResponse,
    XeroStateTokenPayload,
    XeroTenantInfo,
    XeroTokenResponse,
)


class TestXeroModels:
    """Test suite for Xero integration Pydantic models."""

    def test_xero_auth_url_response_valid(self) -> None:
        """Test XeroAuthUrlResponse with valid data."""
        # Arrange
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)
        data = {
            "auth_url": "https://login.xero.com/identity/connect/authorize?...",
            "expires_at": expires_at,
            "organization_id": "test-org-id",
        }

        # Act
        response = XeroAuthUrlResponse(**data)

        # Assert
        assert response.auth_url == data["auth_url"]
        assert response.expires_at == expires_at
        assert response.organization_id == "test-org-id"

    def test_xero_auth_url_response_invalid(self) -> None:
        """Test XeroAuthUrlResponse with invalid data."""
        # Arrange
        data = {
            "auth_url": "",  # Empty URL should fail
            "expires_at": "invalid-date",
            "organization_id": "",
        }

        # Act & Assert
        with pytest.raises(ValidationError):
            XeroAuthUrlResponse(**data)

    def test_xero_connection_status_from_prisma_connected(self) -> None:
        """Test creating XeroConnectionStatus from connected Prisma model."""
        # Arrange
        mock_connection = Mock(spec=XeroConnection)
        mock_connection.connectionStatus = XeroConnectionStatus.connected
        mock_connection.expiresAt = datetime.now(timezone.utc) + timedelta(hours=1)
        mock_connection.xeroTenantId = "test-tenant-id"
        mock_connection.tenantName = "Test Organization"
        mock_connection.lastRefreshedAt = datetime.now(timezone.utc)
        mock_connection.createdAt = datetime.now(timezone.utc) - timedelta(days=1)
        mock_connection.lastError = None
        mock_connection.refreshAttempts = 0

        # Act
        status = XeroConnectionStatusModel.from_prisma(mock_connection)

        # Assert
        assert status.connected is True
        assert status.status == "connected"
        assert status.tenant_id == "test-tenant-id"
        assert status.tenant_name == "Test Organization"
        assert status.last_error is None

    def test_xero_connection_status_from_prisma_expired(self) -> None:
        """Test creating XeroConnectionStatus from expired Prisma model."""
        # Arrange
        mock_connection = Mock(spec=XeroConnection)
        mock_connection.connectionStatus = XeroConnectionStatus.connected
        mock_connection.expiresAt = datetime.now(timezone.utc) - timedelta(hours=1)  # Expired
        mock_connection.xeroTenantId = "test-tenant-id"
        mock_connection.tenantName = "Test Organization"
        mock_connection.lastRefreshedAt = datetime.now(timezone.utc) - timedelta(hours=2)
        mock_connection.createdAt = datetime.now(timezone.utc) - timedelta(days=1)
        mock_connection.lastError = "Token expired"
        mock_connection.refreshAttempts = 1

        # Act
        status = XeroConnectionStatusModel.from_prisma(mock_connection)

        # Assert
        assert status.connected is False  # Token expired
        assert status.status == "connected"  # Status still shows connected
        assert status.tenant_id == "test-tenant-id"
        assert status.last_error == "Token expired"

    def test_xero_connection_status_from_prisma_none(self) -> None:
        """Test creating XeroConnectionStatus from None (no connection)."""
        # Act
        status = XeroConnectionStatusModel.from_prisma(None)

        # Assert
        assert status.connected is False
        assert status.status == "DISCONNECTED"
        assert status.tenant_id is None
        assert status.tenant_name is None
        assert status.expires_at is None
        assert status.last_refreshed_at is None
        assert status.connected_at is None
        assert status.last_error is None
        assert status.refresh_attempts is None

    def test_xero_callback_params_success(self) -> None:
        """Test XeroCallbackParams with success parameters."""
        # Arrange
        data = {
            "code": "test-auth-code-12345",
            "state": "test-jwt-state-token",
        }

        # Act
        params = XeroCallbackParams(**data)

        # Assert
        assert params.code == "test-auth-code-12345"
        assert params.state == "test-jwt-state-token"
        assert params.error is None
        assert params.error_description is None

    def test_xero_callback_params_error(self) -> None:
        """Test XeroCallbackParams with error parameters."""
        # Arrange
        data = {
            "error": "access_denied",
            "error_description": "User denied authorization",
            "state": "test-jwt-state-token",
        }

        # Act
        params = XeroCallbackParams(**data)

        # Assert
        assert params.code is None
        assert params.error == "access_denied"
        assert params.error_description == "User denied authorization"
        assert params.state == "test-jwt-state-token"

    def test_xero_callback_params_optional_fields(self) -> None:
        """Test XeroCallbackParams with all optional fields."""
        # Act
        params = XeroCallbackParams()

        # Assert
        assert params.code is None
        assert params.state is None
        assert params.error is None
        assert params.error_description is None

    def test_xero_token_response_valid(self) -> None:
        """Test XeroTokenResponse with valid token data."""
        # Arrange
        data = {
            "access_token": "test-access-token-12345",
            "refresh_token": "test-refresh-token-12345",
            "expires_in": 1800,
            "token_type": "Bearer",
            "scope": "openid profile email accounting.transactions",
        }

        # Act
        token_response = XeroTokenResponse(**data)

        # Assert
        assert token_response.access_token == "test-access-token-12345"
        assert token_response.refresh_token == "test-refresh-token-12345"
        assert token_response.expires_in == 1800
        assert token_response.token_type == "Bearer"
        assert token_response.scope == "openid profile email accounting.transactions"

    def test_xero_token_response_minimal(self) -> None:
        """Test XeroTokenResponse with minimal required fields."""
        # Arrange
        data = {
            "access_token": "test-access-token",
            "refresh_token": "test-refresh-token",
            "expires_in": 1800,
        }

        # Act
        token_response = XeroTokenResponse(**data)

        # Assert
        assert token_response.access_token == "test-access-token"
        assert token_response.refresh_token == "test-refresh-token"
        assert token_response.expires_in == 1800
        assert token_response.token_type == "Bearer"  # Default value
        assert token_response.scope is None

    def test_xero_tenant_info_valid(self) -> None:
        """Test XeroTenantInfo with valid tenant data."""
        # Arrange
        created_date = datetime(2024, 1, 1, 0, 0, 0)
        updated_date = datetime(2024, 1, 2, 0, 0, 0)
        data = {
            "id": "test-connection-uuid",
            "tenantId": "test-tenant-id",
            "tenantName": "Test Organization",
            "tenantType": "ORGANISATION",
            "createdDateUtc": created_date,
            "updatedDateUtc": updated_date,
        }

        # Act
        tenant_info = XeroTenantInfo(**data)

        # Assert
        assert tenant_info.id == "test-connection-uuid"
        assert tenant_info.tenantId == "test-tenant-id"
        assert tenant_info.tenantName == "Test Organization"
        assert tenant_info.tenantType == "ORGANISATION"
        assert tenant_info.createdDateUtc == created_date
        assert tenant_info.updatedDateUtc == updated_date

    def test_xero_state_token_payload_valid(self) -> None:
        """Test XeroStateTokenPayload with valid data."""
        # Arrange
        issued_at = datetime.now(timezone.utc)
        expires_at = issued_at + timedelta(minutes=30)
        data = {
            "org_id": "test-org-id",
            "user_id": "test-profile-id",
            "csrf_token": "test-csrf-token-12345",
            "issued_at": issued_at,
            "expires_at": expires_at,
        }

        # Act
        payload = XeroStateTokenPayload(**data)

        # Assert
        assert payload.org_id == "test-org-id"
        assert payload.user_id == "test-profile-id"
        assert payload.csrf_token == "test-csrf-token-12345"
        assert payload.issued_at == issued_at
        assert payload.expires_at == expires_at

    def test_xero_disconnect_response_valid(self) -> None:
        """Test XeroDisconnectResponse with valid data."""
        # Arrange
        disconnected_at = datetime.now(timezone.utc)
        data = {
            "message": "Xero connection disconnected successfully",
            "disconnected_at": disconnected_at,
            "organization_id": "test-org-id",
        }

        # Act
        response = XeroDisconnectResponse(**data)

        # Assert
        assert response.message == "Xero connection disconnected successfully"
        assert response.disconnected_at == disconnected_at
        assert response.organization_id == "test-org-id"

    def test_xero_connection_response_valid(self) -> None:
        """Test XeroConnectionResponse with valid data."""
        # Arrange
        connected_at = datetime.now(timezone.utc)
        data = {
            "message": "Xero connection established successfully",
            "connected_at": connected_at,
            "tenant_name": "Test Organization",
            "organization_id": "test-org-id",
        }

        # Act
        response = XeroConnectionResponse(**data)

        # Assert
        assert response.message == "Xero connection established successfully"
        assert response.connected_at == connected_at
        assert response.tenant_name == "Test Organization"
        assert response.organization_id == "test-org-id"

    def test_xero_error_response_valid(self) -> None:
        """Test XeroErrorResponse with valid data."""
        # Arrange
        data = {
            "detail": "Connection failed",
            "error_code": "XERO_CONNECTION_ERROR",
        }

        # Act
        response = XeroErrorResponse(**data)

        # Assert
        assert response.detail == "Connection failed"
        assert response.error_code == "XERO_CONNECTION_ERROR"
        assert response.timestamp is not None

    def test_xero_error_response_minimal(self) -> None:
        """Test XeroErrorResponse with minimal required fields."""
        # Arrange
        data = {
            "detail": "Something went wrong",
        }

        # Act
        response = XeroErrorResponse(**data)

        # Assert
        assert response.detail == "Something went wrong"
        assert response.error_code is None
        assert response.timestamp is not None

    def test_model_serialization(self) -> None:
        """Test that all models can be properly serialized to JSON."""
        # Arrange
        models_to_test = [
            XeroAuthUrlResponse(
                auth_url="https://example.com",
                expires_at=datetime.now(timezone.utc),
                organization_id="test-org",
            ),
            XeroConnectionStatusModel(
                connected=True,
                status="connected",
                tenant_id="test-tenant",
                tenant_name="Test Org",
                expires_at=datetime.now(timezone.utc),
                last_refreshed_at=datetime.now(timezone.utc),
                connected_at=datetime.now(timezone.utc),
                last_error=None,
                refresh_attempts=0,
            ),
            XeroTokenResponse(
                access_token="token",
                refresh_token="refresh",
                expires_in=1800,
            ),
        ]

        # Act & Assert
        for model in models_to_test:
            json_data = model.model_dump(mode="json")
            assert isinstance(json_data, dict)

            # Verify model can be reconstructed from JSON
            reconstructed = type(model)(**json_data)
            assert reconstructed == model
