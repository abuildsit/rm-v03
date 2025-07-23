"""
Tests for XeroDataService batch payment functionality.
"""

from decimal import Decimal
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from src.domains.external_accounting.base.types import BatchPaymentData
from src.domains.external_accounting.xero.data_service import XeroDataService
from src.shared.exceptions import IntegrationConnectionError

# Fixtures are passed as parameters to test methods


class TestXeroDataServiceBatchPayment:
    """Test suite for XeroDataService batch payment functionality."""

    @pytest.fixture
    def xero_data_service(self, mock_prisma: Mock) -> XeroDataService:
        """Create XeroDataService instance with mocked database."""
        return XeroDataService(mock_prisma)

    @pytest.fixture
    def mock_xero_connection(self) -> Mock:
        """Mock active Xero connection."""
        connection = Mock()
        connection.xeroTenantId = "test-tenant-id"
        return connection

    @pytest.mark.asyncio
    async def test_create_batch_payment_success(
        self,
        xero_data_service: XeroDataService,
        mock_prisma: Mock,
        mock_xero_connection: Mock,
        mock_batch_payment_data,
        mock_xero_batch_payment_response,
    ) -> None:
        """Test successful batch payment creation."""
        # Arrange
        org_id = "test-org-123"

        # Mock database connection lookup
        mock_prisma.xeroconnection.find_first.return_value = mock_xero_connection

        # Mock XeroService for token validation
        mock_access_token = "valid-access-token"
        with patch.object(
            xero_data_service.xero_service,
            "get_valid_access_token",
            return_value=mock_access_token,
        ):
            # Mock HTTP client response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_xero_batch_payment_response
            mock_response.raise_for_status.return_value = None

            with patch("httpx.AsyncClient") as mock_client:
                mock_client_instance = AsyncMock()
                mock_client.return_value.__aenter__.return_value = mock_client_instance
                mock_client_instance.request.return_value = mock_response

                # Act
                result = await xero_data_service.create_batch_payment(
                    org_id, mock_batch_payment_data
                )

                # Assert
                assert result.success is True
                assert result.batch_id == "test-batch-payment-123"
                assert result.error_message is None

                # Verify correct API call was made
                mock_client_instance.request.assert_called_once()
                call_args = mock_client_instance.request.call_args

                assert call_args[0][0] == "PUT"  # HTTP method
                assert (
                    call_args[0][1] == "https://api.xero.com/api.xro/2.0/BatchPayments"
                )

                # Verify headers
                headers = call_args[1]["headers"]
                assert headers["Authorization"] == f"Bearer {mock_access_token}"
                assert headers["Xero-Tenant-Id"] == "test-tenant-id"
                # Note: Content-Type may be set by httpx automatically for JSON requests

                # Verify request body structure
                request_body = call_args[1]["json"]
                assert request_body["Account"]["AccountID"] == "test-account-123"
                assert request_body["Date"] == "2024-01-15"
                assert request_body["Reference"] == "RM: Batch Payment REF-12345"
                assert len(request_body["Payments"]) == 2

    @pytest.mark.asyncio
    async def test_create_batch_payment_api_error(
        self,
        xero_data_service: XeroDataService,
        mock_prisma: Mock,
        mock_xero_connection: Mock,
        mock_batch_payment_data,
    ) -> None:
        """Test batch payment creation with API error."""
        # Arrange
        org_id = "test-org-123"
        mock_prisma.xeroconnection.find_first.return_value = mock_xero_connection

        with patch.object(
            xero_data_service.xero_service,
            "get_valid_access_token",
            return_value="valid-access-token",
        ):
            # Mock HTTP error response
            mock_response = Mock()
            mock_response.status_code = 400
            mock_response.text = "Invoice not found"
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Bad Request", request=Mock(), response=mock_response
            )

            with patch("httpx.AsyncClient") as mock_client:
                mock_client_instance = AsyncMock()
                mock_client.return_value.__aenter__.return_value = mock_client_instance
                mock_client_instance.request.return_value = mock_response

                # Act & Assert
                with pytest.raises(IntegrationConnectionError) as exc_info:
                    await xero_data_service.create_batch_payment(
                        org_id, mock_batch_payment_data
                    )

                assert "Xero API request failed" in str(exc_info.value)
                assert "Invoice not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_create_batch_payment_auth_error(
        self,
        xero_data_service: XeroDataService,
        mock_prisma: Mock,
        mock_xero_connection: Mock,
        mock_batch_payment_data,
    ) -> None:
        """Test batch payment creation with authentication error."""
        # Arrange
        org_id = "test-org-123"
        mock_prisma.xeroconnection.find_first.return_value = mock_xero_connection

        with patch.object(
            xero_data_service.xero_service,
            "get_valid_access_token",
            return_value="invalid-access-token",
        ):
            # Mock 401 error response
            mock_response = Mock()
            mock_response.status_code = 401
            mock_response.text = "Unauthorized"
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Unauthorized", request=Mock(), response=mock_response
            )

            with patch("httpx.AsyncClient") as mock_client:
                mock_client_instance = AsyncMock()
                mock_client.return_value.__aenter__.return_value = mock_client_instance
                mock_client_instance.request.return_value = mock_response

                # Act & Assert
                # Note: 401 errors trigger retry logic, eventually
                # raising max retries error
                with pytest.raises(IntegrationConnectionError) as exc_info:
                    await xero_data_service.create_batch_payment(
                        org_id, mock_batch_payment_data
                    )

                assert "Max retries exceeded" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_create_batch_payment_retry_logic(
        self,
        xero_data_service: XeroDataService,
        mock_prisma: Mock,
        mock_xero_connection: Mock,
        mock_batch_payment_data,
        mock_xero_batch_payment_response,
    ) -> None:
        """Test batch payment creation with retry logic."""
        # Arrange
        org_id = "test-org-123"
        mock_prisma.xeroconnection.find_first.return_value = mock_xero_connection

        with patch.object(
            xero_data_service.xero_service,
            "get_valid_access_token",
            return_value="valid-access-token",
        ):
            # Mock first two calls fail with 429 (rate limit), third succeeds
            mock_rate_limit_response = Mock()
            mock_rate_limit_response.status_code = 429
            mock_rate_limit_response.headers = {"Retry-After": "1"}

            mock_success_response = Mock()
            mock_success_response.status_code = 200
            mock_success_response.json.return_value = mock_xero_batch_payment_response
            mock_success_response.raise_for_status.return_value = None

            with patch("httpx.AsyncClient") as mock_client:
                mock_client_instance = AsyncMock()
                mock_client.return_value.__aenter__.return_value = mock_client_instance

                # First two calls return 429, third returns 200
                mock_client_instance.request.side_effect = [
                    mock_rate_limit_response,
                    mock_rate_limit_response,
                    mock_success_response,
                ]

                with patch("asyncio.sleep") as mock_sleep:
                    # Act
                    result = await xero_data_service.create_batch_payment(
                        org_id, mock_batch_payment_data
                    )

                    # Assert
                    assert result.success is True
                    assert result.batch_id == "test-batch-payment-123"

                    # Verify retry attempts
                    assert mock_client_instance.request.call_count == 3
                    assert mock_sleep.call_count == 2  # Sleep after first two failures

    @pytest.mark.asyncio
    async def test_create_batch_payment_no_connection(
        self,
        xero_data_service: XeroDataService,
        mock_prisma: Mock,
        mock_batch_payment_data,
    ) -> None:
        """Test batch payment creation with no active Xero connection."""
        # Arrange
        org_id = "test-org-123"
        mock_prisma.xeroconnection.find_first.return_value = None

        # Act & Assert
        with pytest.raises(IntegrationConnectionError) as exc_info:
            await xero_data_service.create_batch_payment(
                org_id, mock_batch_payment_data
            )

        assert "No Xero connection found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_create_batch_payment_empty_response(
        self,
        xero_data_service: XeroDataService,
        mock_prisma: Mock,
        mock_xero_connection: Mock,
        mock_batch_payment_data,
    ) -> None:
        """Test batch payment creation with empty response from Xero."""
        # Arrange
        org_id = "test-org-123"
        mock_prisma.xeroconnection.find_first.return_value = mock_xero_connection

        with patch.object(
            xero_data_service.xero_service,
            "get_valid_access_token",
            return_value="valid-access-token",
        ):
            # Mock empty response
            empty_response = {"BatchPayments": []}
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = empty_response
            mock_response.raise_for_status.return_value = None

            with patch("httpx.AsyncClient") as mock_client:
                mock_client_instance = AsyncMock()
                mock_client.return_value.__aenter__.return_value = mock_client_instance
                mock_client_instance.request.return_value = mock_response

                # Act & Assert
                with pytest.raises(IntegrationConnectionError) as exc_info:
                    await xero_data_service.create_batch_payment(
                        org_id, mock_batch_payment_data
                    )

                assert "No batch payment returned from Xero API" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_create_batch_payment_data_mapping(
        self,
        xero_data_service: XeroDataService,
        mock_prisma: Mock,
        mock_xero_connection: Mock,
        mock_xero_batch_payment_response,
    ) -> None:
        """Test correct data mapping from BatchPaymentData to Xero format."""
        # Arrange
        org_id = "test-org-123"
        mock_prisma.xeroconnection.find_first.return_value = mock_xero_connection

        from src.domains.external_accounting.base.types import PaymentItem

        batch_data = BatchPaymentData(
            account_id="mapped-account-456",
            payment_date="2024-02-20",
            payment_reference="RM: Custom Reference",
            payments=[
                PaymentItem(
                    invoice_id="mapped-invoice-1",
                    amount=Decimal("75.25"),
                    reference="Custom payment ref 1",
                ),
                PaymentItem(
                    invoice_id="mapped-invoice-2",
                    amount=Decimal("124.75"),
                    reference="Custom payment ref 2",
                ),
            ],
        )

        with patch.object(
            xero_data_service.xero_service,
            "get_valid_access_token",
            return_value="valid-access-token",
        ):
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_xero_batch_payment_response
            mock_response.raise_for_status.return_value = None

            with patch("httpx.AsyncClient") as mock_client:
                mock_client_instance = AsyncMock()
                mock_client.return_value.__aenter__.return_value = mock_client_instance
                mock_client_instance.request.return_value = mock_response

                # Act
                await xero_data_service.create_batch_payment(org_id, batch_data)

                # Assert - verify correct mapping in request body
                call_args = mock_client_instance.request.call_args
                request_body = call_args[1]["json"]

                assert request_body["Account"]["AccountID"] == "mapped-account-456"
                assert request_body["Date"] == "2024-02-20"
                assert request_body["Reference"] == "RM: Custom Reference"

                payments = request_body["Payments"]
                assert len(payments) == 2
                assert payments[0]["Invoice"]["InvoiceID"] == "mapped-invoice-1"
                assert payments[0]["Amount"] == "75.25"
                assert payments[0]["Reference"] == "Custom payment ref 1"
                assert payments[1]["Invoice"]["InvoiceID"] == "mapped-invoice-2"
                assert payments[1]["Amount"] == "124.75"
                assert payments[1]["Reference"] == "Custom payment ref 2"
