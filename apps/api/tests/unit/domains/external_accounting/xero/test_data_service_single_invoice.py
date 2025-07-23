"""
Tests for XeroDataService single invoice fetch functionality.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from httpx import HTTPStatusError

from src.domains.external_accounting.base.types import BaseInvoiceFilters
from src.domains.external_accounting.xero.data_service import XeroDataService
from src.shared.exceptions import IntegrationConnectionError


class TestXeroDataServiceSingleInvoice:
    """Test suite for XeroDataService single invoice functionality."""

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

    @pytest.fixture
    def mock_single_invoice_response(self) -> dict:
        """Mock Xero API response for single invoice."""
        return {
            "Invoices": [
                {
                    "InvoiceID": "test-invoice-123",
                    "InvoiceNumber": "INV-001",
                    "Type": "ACCREC",
                    "Contact": {
                        "ContactID": "test-contact-123",
                        "Name": "Test Customer",
                        "ContactStatus": "ACTIVE",
                    },
                    "Date": "/Date(1704067200000+0000)/",
                    "DueDate": "/Date(1706745600000+0000)/",
                    "Status": "AUTHORISED",
                    "LineAmountTypes": "Exclusive",
                    "SubTotal": 100.00,
                    "TotalTax": 10.00,
                    "Total": 110.00,
                    "AmountDue": 110.00,
                    "AmountPaid": 0.00,
                    "AmountCredited": 0.00,
                    "CurrencyCode": "AUD",
                    "LineItems": [
                        {
                            "Description": "Test Item",
                            "UnitAmount": 100.00,
                            "Quantity": 1.0,
                            "LineAmount": 100.00,
                            "AccountCode": "200",
                        }
                    ],
                    "UpdatedDateUTC": "/Date(1704067200000+0000)/",
                    "CreatedDateUTC": "/Date(1704067200000+0000)/",
                }
            ]
        }

    @pytest.mark.asyncio
    async def test_get_invoices_with_invoice_id_success(
        self,
        xero_data_service: XeroDataService,
        mock_prisma: Mock,
        mock_xero_connection: Mock,
        mock_single_invoice_response: dict,
    ) -> None:
        """Test successful single invoice fetch by ID."""
        # Arrange
        org_id = "test-org-123"
        invoice_id = "test-invoice-123"
        filters = BaseInvoiceFilters()

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
            mock_response.json.return_value = mock_single_invoice_response
            mock_response.raise_for_status.return_value = None

            with patch("httpx.AsyncClient") as mock_client:
                mock_client_instance = AsyncMock()
                mock_client.return_value.__aenter__.return_value = mock_client_instance
                mock_client_instance.request.return_value = mock_response

                # Act
                result = await xero_data_service.get_invoices(
                    org_id, filters, invoice_id=invoice_id
                )

                # Assert
                assert len(result) == 1
                assert result[0].InvoiceID == "test-invoice-123"
                assert result[0].InvoiceNumber == "INV-001"
                assert result[0].Status == "AUTHORISED"

                # Verify correct API endpoint was called
                mock_client_instance.request.assert_called_once()
                call_args = mock_client_instance.request.call_args
                assert call_args[0][0] == "GET"  # HTTP method
                assert (
                    call_args[0][1]
                    == f"https://api.xero.com/api.xro/2.0/Invoices/{invoice_id}"
                )

                # Verify headers
                headers = call_args[1]["headers"]
                assert headers["Authorization"] == f"Bearer {mock_access_token}"
                assert headers["Xero-Tenant-Id"] == "test-tenant-id"

    @pytest.mark.asyncio
    async def test_get_invoices_with_invoice_id_not_found(
        self,
        xero_data_service: XeroDataService,
        mock_prisma: Mock,
        mock_xero_connection: Mock,
    ) -> None:
        """Test handling when invoice ID is not found."""
        # Arrange
        org_id = "test-org-123"
        invoice_id = "nonexistent-invoice-id"
        filters = BaseInvoiceFilters()

        mock_prisma.xeroconnection.find_first.return_value = mock_xero_connection

        with patch.object(
            xero_data_service.xero_service,
            "get_valid_access_token",
            return_value="valid-access-token",
        ):
            # Mock 404 error response
            mock_response = Mock()
            mock_response.status_code = 404
            mock_response.text = "Invoice not found"
            mock_response.raise_for_status.side_effect = HTTPStatusError(
                "Not Found", request=Mock(), response=mock_response
            )

            with patch("httpx.AsyncClient") as mock_client:
                mock_client_instance = AsyncMock()
                mock_client.return_value.__aenter__.return_value = mock_client_instance
                mock_client_instance.request.return_value = mock_response

                # Act & Assert
                with pytest.raises(IntegrationConnectionError) as exc_info:
                    await xero_data_service.get_invoices(
                        org_id, filters, invoice_id=invoice_id
                    )

                assert "Xero API request failed" in str(exc_info.value)
                assert "Invoice not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_invoices_bulk_unchanged(
        self,
        xero_data_service: XeroDataService,
        mock_prisma: Mock,
        mock_xero_connection: Mock,
    ) -> None:
        """Test bulk invoice fetch still works without invoice_id parameter."""
        # Arrange
        org_id = "test-org-123"
        filters = BaseInvoiceFilters(status=["AUTHORISED"])

        mock_prisma.xeroconnection.find_first.return_value = mock_xero_connection

        # Mock bulk response (existing functionality)
        bulk_response = {
            "Invoices": [
                {
                    "InvoiceID": "invoice-1",
                    "InvoiceNumber": "INV-001",
                    "Type": "ACCREC",
                    "Contact": {
                        "ContactID": "contact-1",
                        "Name": "Customer 1",
                        "ContactStatus": "ACTIVE",
                    },
                    "Date": "/Date(1704067200000+0000)/",
                    "Status": "AUTHORISED",
                    "LineAmountTypes": "Exclusive",
                    "SubTotal": 100.00,
                    "TotalTax": 10.00,
                    "Total": 110.00,
                    "CurrencyCode": "AUD",
                    "LineItems": [],
                },
                {
                    "InvoiceID": "invoice-2",
                    "InvoiceNumber": "INV-002",
                    "Type": "ACCREC",
                    "Contact": {
                        "ContactID": "contact-2",
                        "Name": "Customer 2",
                        "ContactStatus": "ACTIVE",
                    },
                    "Date": "/Date(1704067200000+0000)/",
                    "Status": "AUTHORISED",
                    "LineAmountTypes": "Exclusive",
                    "SubTotal": 200.00,
                    "TotalTax": 20.00,
                    "Total": 220.00,
                    "CurrencyCode": "AUD",
                    "LineItems": [],
                },
            ]
        }

        with patch.object(
            xero_data_service.xero_service,
            "get_valid_access_token",
            return_value="valid-access-token",
        ):
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = bulk_response
            mock_response.raise_for_status.return_value = None

            with patch("httpx.AsyncClient") as mock_client:
                mock_client_instance = AsyncMock()
                mock_client.return_value.__aenter__.return_value = mock_client_instance
                mock_client_instance.request.return_value = mock_response

                # Act - call without invoice_id parameter
                result = await xero_data_service.get_invoices(org_id, filters)

                # Assert
                assert len(result) == 2
                assert result[0].InvoiceID == "invoice-1"
                assert result[1].InvoiceID == "invoice-2"

                # Verify bulk endpoint was called (not single invoice)
                mock_client_instance.request.assert_called_once()
                call_args = mock_client_instance.request.call_args
                assert call_args[0][1] == "https://api.xero.com/api.xro/2.0/Invoices"

                # Verify filters were applied in params
                params = call_args[1].get("params")
                assert params is not None
                # The where clause should contain status filter
                where_clause = params.where if hasattr(params, "where") else None
                if where_clause:
                    assert 'Status=="AUTHORISED"' in where_clause

    @pytest.mark.asyncio
    async def test_get_invoices_with_invoice_id_empty_response(
        self,
        xero_data_service: XeroDataService,
        mock_prisma: Mock,
        mock_xero_connection: Mock,
    ) -> None:
        """Test handling empty response for single invoice request."""
        # Arrange
        org_id = "test-org-123"
        invoice_id = "test-invoice-123"
        filters = BaseInvoiceFilters()

        mock_prisma.xeroconnection.find_first.return_value = mock_xero_connection

        with patch.object(
            xero_data_service.xero_service,
            "get_valid_access_token",
            return_value="valid-access-token",
        ):
            # Mock empty response
            empty_response = {"Invoices": []}
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = empty_response
            mock_response.raise_for_status.return_value = None

            with patch("httpx.AsyncClient") as mock_client:
                mock_client_instance = AsyncMock()
                mock_client.return_value.__aenter__.return_value = mock_client_instance
                mock_client_instance.request.return_value = mock_response

                # Act
                result = await xero_data_service.get_invoices(
                    org_id, filters, invoice_id=invoice_id
                )

                # Assert
                assert len(result) == 0
                assert result == []

    @pytest.mark.asyncio
    async def test_get_invoices_with_invoice_id_no_connection(
        self,
        xero_data_service: XeroDataService,
        mock_prisma: Mock,
    ) -> None:
        """Test single invoice fetch with no active Xero connection."""
        # Arrange
        org_id = "test-org-123"
        invoice_id = "test-invoice-123"
        filters = BaseInvoiceFilters()

        mock_prisma.xeroconnection.find_first.return_value = None

        # Act & Assert
        with pytest.raises(IntegrationConnectionError) as exc_info:
            await xero_data_service.get_invoices(org_id, filters, invoice_id=invoice_id)

        assert "No Xero connection found for this organization" in str(exc_info.value)
