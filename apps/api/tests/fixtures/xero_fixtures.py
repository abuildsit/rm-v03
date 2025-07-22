# tests/fixtures/xero_fixtures.py
"""Test fixtures for Xero integration tests."""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
from unittest.mock import Mock

import pytest
from prisma.enums import XeroConnectionStatus
from prisma.models import XeroConnection


@pytest.fixture
def mock_xero_connection() -> Mock:
    """Mock XeroConnection with active status."""
    connection = Mock(spec=XeroConnection)
    connection.id = "test-connection-id"
    connection.organizationId = "test-org-id"
    connection.xeroTenantId = "test-tenant-id"
    connection.tenantName = "Test Organization"
    connection.tenantType = "ORGANISATION"
    connection.accessToken = "test-access-token"
    connection.refreshToken = "test-refresh-token"
    connection.expiresAt = datetime.now(timezone.utc) + timedelta(hours=1)
    connection.connectionStatus = XeroConnectionStatus.connected
    connection.lastError = None
    connection.lastRefreshedAt = datetime.now(timezone.utc) - timedelta(minutes=30)
    connection.refreshAttempts = 0
    connection.scopes = ["openid", "profile", "email", "accounting.transactions"]
    connection.authEventId = "test-auth-event-id"
    connection.lastSyncAt = None
    connection.syncStatus = None
    connection.syncError = None
    connection.createdBy = "test-profile-id"
    connection.createdAt = datetime.now(timezone.utc) - timedelta(days=1)
    connection.updatedAt = datetime.now(timezone.utc)
    return connection


@pytest.fixture
def mock_expired_xero_connection() -> Mock:
    """Mock XeroConnection with expired token."""
    connection = Mock(spec=XeroConnection)
    connection.id = "test-connection-id"
    connection.organizationId = "test-org-id"
    connection.xeroTenantId = "test-tenant-id"
    connection.tenantName = "Test Organization"
    connection.tenantType = "ORGANISATION"
    connection.accessToken = "expired-access-token"
    connection.refreshToken = "test-refresh-token"
    connection.expiresAt = datetime.now(timezone.utc) - timedelta(hours=1)  # Expired
    connection.connectionStatus = XeroConnectionStatus.expired
    connection.lastError = "Token expired"
    connection.lastRefreshedAt = datetime.now(timezone.utc) - timedelta(hours=2)
    connection.refreshAttempts = 0
    connection.scopes = ["openid", "profile", "email", "accounting.transactions"]
    connection.createdBy = "test-profile-id"
    connection.createdAt = datetime.now(timezone.utc) - timedelta(days=1)
    connection.updatedAt = datetime.now(timezone.utc) - timedelta(hours=1)
    return connection


@pytest.fixture
def mock_revoked_xero_connection() -> Mock:
    """Mock XeroConnection with revoked status."""
    connection = Mock(spec=XeroConnection)
    connection.id = "test-connection-id"
    connection.organizationId = "test-org-id"
    connection.xeroTenantId = "test-tenant-id"
    connection.tenantName = "Test Organization"
    connection.tenantType = "ORGANISATION"
    connection.accessToken = "revoked-access-token"
    connection.refreshToken = "revoked-refresh-token"
    connection.expiresAt = datetime.now(timezone.utc) + timedelta(hours=1)
    connection.connectionStatus = XeroConnectionStatus.revoked
    connection.lastError = None
    connection.lastRefreshedAt = datetime.now(timezone.utc) - timedelta(days=1)
    connection.refreshAttempts = 0
    connection.scopes = ["openid", "profile", "email", "accounting.transactions"]
    connection.createdBy = "test-profile-id"
    connection.createdAt = datetime.now(timezone.utc) - timedelta(days=1)
    connection.updatedAt = datetime.now(timezone.utc)
    return connection


@pytest.fixture
def xero_token_response_data() -> Dict[str, Any]:
    """Mock Xero token response data."""
    return {
        "access_token": "test-access-token-12345",
        "refresh_token": "test-refresh-token-12345",
        "expires_in": 1800,  # 30 minutes
        "token_type": "Bearer",
        "scope": (
            "openid profile email accounting.transactions "
            "accounting.settings offline_access"
        ),
    }


@pytest.fixture
def xero_tenant_info_data() -> Dict[str, Any]:
    """Mock Xero tenant information."""
    return {
        "id": "test-connection-uuid",
        "tenantId": "test-tenant-id",
        "tenantName": "Test Organization",
        "tenantType": "ORGANISATION",
        "createdDateUtc": "2024-01-01T00:00:00.000Z",
        "updatedDateUtc": "2024-01-01T00:00:00.000Z",
    }


@pytest.fixture
def xero_connections_response_data(
    xero_tenant_info_data: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Mock Xero connections API response."""
    return [xero_tenant_info_data]


@pytest.fixture
def xero_error_response_data() -> Dict[str, Any]:
    """Mock Xero error response."""
    return {
        "error": "invalid_grant",
        "error_description": "The authorization code has expired or been used already.",
    }


@pytest.fixture
def xero_oauth_callback_success_params() -> Dict[str, str]:
    """Mock successful OAuth callback parameters."""
    return {
        "code": "test-auth-code-12345",
        "state": "test-jwt-state-token",
    }


@pytest.fixture
def xero_oauth_callback_error_params() -> Dict[str, str]:
    """Mock OAuth callback with error parameters."""
    return {
        "error": "access_denied",
        "error_description": "User denied authorization",
        "state": "test-jwt-state-token",
    }


@pytest.fixture
def mock_jwt_state_token_payload() -> Dict[str, Any]:
    """Mock JWT state token payload."""
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)
    return {
        "org_id": "test-org-id",
        "user_id": "test-profile-id",
        "csrf_token": "test-csrf-token-12345",
        "issued_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": expires_at.isoformat(),
    }


@pytest.fixture
def xero_auth_url() -> str:
    """Mock Xero authorization URL."""
    return (
        "https://login.xero.com/identity/connect/authorize"
        "?response_type=code&client_id=test-client-id"
        "&redirect_uri=http://localhost:3000/callback"
        "&scope=openid+profile+email+accounting.transactions+"
        "accounting.settings+offline_access&state=test-jwt-state-token"
    )


class MockHttpResponse:
    """Mock HTTP response for testing."""

    def __init__(self, json_data: Dict[str, Any], status_code: int = 200):
        self.json_data = json_data
        self.status_code = status_code
        self.text = str(json_data)

    def json(self) -> Dict[str, Any]:
        return self.json_data

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            from httpx import HTTPStatusError, Request, Response

            request = Mock(spec=Request)
            response = Mock(spec=Response)
            response.status_code = self.status_code
            response.text = self.text
            raise HTTPStatusError(
                message=f"HTTP {self.status_code}",
                request=request,
                response=response,
            )


def create_mock_http_response(
    json_data: Dict[str, Any], status_code: int = 200
) -> MockHttpResponse:
    """Create a mock HTTP response."""
    return MockHttpResponse(json_data, status_code)


@pytest.fixture
def mock_settings():
    """Mock settings for Xero configuration."""
    settings_mock = Mock()
    settings_mock.XERO_CLIENT_ID = "test-client-id"
    settings_mock.XERO_CLIENT_SECRET = "test-client-secret"
    settings_mock.XERO_REDIRECT_URI = "http://localhost:3000/callback"
    settings_mock.XERO_SCOPES = (
        "openid profile email accounting.transactions "
        "accounting.settings offline_access"
    )
    settings_mock.jwt_secret = "test-jwt-secret-for-state-tokens"
    return settings_mock
