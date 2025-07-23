"""
Tests for invoice sync functionality after batch payment creation.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.domains.remittances.service import _sync_batch_payment_invoices


class TestInvoiceSyncAfterBatchPayment:
    """Test suite for invoice sync after batch payment creation."""

    @pytest.fixture
    def mock_matched_invoices(self) -> list:
        """Mock list of matched invoices with Xero IDs."""
        invoice1 = Mock()
        invoice1.id = "local-invoice-1"
        invoice1.invoiceId = "xero-invoice-1"
        invoice1.invoiceNumber = "INV-001"

        invoice2 = Mock()
        invoice2.id = "local-invoice-2"
        invoice2.invoiceId = "xero-invoice-2"
        invoice2.invoiceNumber = "INV-002"

        invoice3 = Mock()
        invoice3.id = "local-invoice-3"
        invoice3.invoiceId = "xero-invoice-3"
        invoice3.invoiceNumber = "INV-003"

        return [invoice1, invoice2, invoice3]

    @pytest.fixture
    def mock_xero_invoice_responses(self) -> dict:
        """Mock Xero API responses for individual invoices."""
        return {
            "xero-invoice-1": {
                "Invoices": [
                    {
                        "InvoiceID": "xero-invoice-1",
                        "InvoiceNumber": "INV-001",
                        "Type": "ACCREC",
                        "Contact": {
                            "ContactID": "contact-1",
                            "Name": "Customer 1",
                            "ContactStatus": "ACTIVE",
                        },
                        "Date": "/Date(1704067200000+0000)/",
                        "Status": "PAID",  # Updated status after payment
                        "LineAmountTypes": "Exclusive",
                        "SubTotal": 100.00,
                        "TotalTax": 10.00,
                        "Total": 110.00,
                        "AmountDue": 0.00,  # Now fully paid
                        "AmountPaid": 110.00,  # Payment recorded
                        "AmountCredited": 0.00,
                        "CurrencyCode": "AUD",
                        "LineItems": [
                            {
                                "Description": "Test Item 1",
                                "UnitAmount": 100.00,
                                "Quantity": 1.0,
                                "LineAmount": 100.00,
                            }
                        ],
                        "UpdatedDateUTC": "/Date(1704153600000+0000)/",  # Updated
                    }
                ]
            },
            "xero-invoice-2": {
                "Invoices": [
                    {
                        "InvoiceID": "xero-invoice-2",
                        "InvoiceNumber": "INV-002",
                        "Type": "ACCREC",
                        "Contact": {
                            "ContactID": "contact-2",
                            "Name": "Customer 2",
                            "ContactStatus": "ACTIVE",
                        },
                        "Date": "/Date(1704067200000+0000)/",
                        "Status": "PAID",  # Updated status
                        "LineAmountTypes": "Exclusive",
                        "SubTotal": 200.00,
                        "TotalTax": 20.00,
                        "Total": 220.00,
                        "AmountDue": 0.00,  # Fully paid
                        "AmountPaid": 220.00,  # Payment recorded
                        "AmountCredited": 0.00,
                        "CurrencyCode": "AUD",
                        "LineItems": [
                            {
                                "Description": "Test Item 2",
                                "UnitAmount": 200.00,
                                "Quantity": 1.0,
                                "LineAmount": 200.00,
                            }
                        ],
                        "UpdatedDateUTC": "/Date(1704153600000+0000)/",
                    }
                ]
            },
            "xero-invoice-3": {
                "Invoices": [
                    {
                        "InvoiceID": "xero-invoice-3",
                        "InvoiceNumber": "INV-003",
                        "Type": "ACCREC",
                        "Contact": {
                            "ContactID": "contact-3",
                            "Name": "Customer 3",
                            "ContactStatus": "ACTIVE",
                        },
                        "Date": "/Date(1704067200000+0000)/",
                        "Status": "PAID",
                        "LineAmountTypes": "Exclusive",
                        "SubTotal": 150.00,
                        "TotalTax": 15.00,
                        "Total": 165.00,
                        "AmountDue": 0.00,
                        "AmountPaid": 165.00,
                        "AmountCredited": 0.00,
                        "CurrencyCode": "AUD",
                        "LineItems": [
                            {
                                "Description": "Test Item 3",
                                "UnitAmount": 150.00,
                                "Quantity": 1.0,
                                "LineAmount": 150.00,
                            }
                        ],
                        "UpdatedDateUTC": "/Date(1704153600000+0000)/",
                    }
                ]
            },
        }

    @pytest.mark.asyncio
    async def test_sync_batch_payment_invoices_success(
        self,
        mock_prisma: Mock,
        mock_matched_invoices: list,
        mock_xero_invoice_responses: dict,
    ) -> None:
        """Test successful invoice sync for all invoices."""
        # Arrange
        org_id = "test-org-123"

        # Mock data service
        mock_data_service = AsyncMock()

        # Configure data service to return updated invoices
        async def get_invoices_side_effect(org_id, filters, invoice_id=None):
            if invoice_id in mock_xero_invoice_responses:
                return mock_xero_invoice_responses[invoice_id]["Invoices"]
            return []

        mock_data_service.get_invoices.side_effect = get_invoices_side_effect

        # Mock SyncOrchestrator
        with patch(
            "src.domains.remittances.service.SyncOrchestrator"
        ) as mock_orchestrator_class:
            mock_orchestrator = Mock()
            mock_orchestrator_class.return_value = mock_orchestrator

            # Mock successful upsert
            mock_orchestrator._upsert_invoices.return_value = AsyncMock()

            # Act
            await _sync_batch_payment_invoices(
                db=mock_prisma,
                org_id=org_id,
                matched_invoices=mock_matched_invoices,
                data_service=mock_data_service,
            )

            # Assert
            # Verify get_invoices was called for each invoice
            assert mock_data_service.get_invoices.call_count == 3

            # Verify each invoice was fetched with correct parameters
            get_invoices_calls = mock_data_service.get_invoices.call_args_list
            expected_invoice_ids = [
                "xero-invoice-1",
                "xero-invoice-2",
                "xero-invoice-3",
            ]

            for i, call in enumerate(get_invoices_calls):
                args, kwargs = call
                assert kwargs.get("org_id") == org_id  # org_id passed as keyword
                assert kwargs.get("invoice_id") == expected_invoice_ids[i]

            # Verify SyncOrchestrator was created
            mock_orchestrator_class.assert_called_once_with(mock_prisma)

            # Verify _upsert_invoices was called for each successful fetch
            assert mock_orchestrator._upsert_invoices.call_count == 3

            # Verify each upsert call had correct parameters
            upsert_calls = mock_orchestrator._upsert_invoices.call_args_list
            for call in upsert_calls:
                args, kwargs = call
                assert args[0] == org_id  # org_id parameter
                assert len(args[1]) == 1  # Single invoice in list

    @pytest.mark.asyncio
    async def test_sync_partial_failure(
        self,
        mock_prisma: Mock,
        mock_matched_invoices: list,
        mock_xero_invoice_responses: dict,
    ) -> None:
        """Test when some invoices fail to sync."""
        # Arrange
        org_id = "test-org-123"

        # Mock data service with mixed success/failure
        mock_data_service = AsyncMock()

        async def get_invoices_side_effect(org_id, filters, invoice_id=None):
            if invoice_id == "xero-invoice-1":
                # First invoice succeeds
                return mock_xero_invoice_responses[invoice_id]["Invoices"]
            elif invoice_id == "xero-invoice-2":
                # Second invoice fails
                raise Exception("Xero API error: Invoice not found")
            elif invoice_id == "xero-invoice-3":
                # Third invoice succeeds
                return mock_xero_invoice_responses[invoice_id]["Invoices"]
            return []

        mock_data_service.get_invoices.side_effect = get_invoices_side_effect

        # Mock SyncOrchestrator
        with patch(
            "src.domains.remittances.service.SyncOrchestrator"
        ) as mock_orchestrator_class:
            mock_orchestrator = Mock()
            mock_orchestrator_class.return_value = mock_orchestrator
            mock_orchestrator._upsert_invoices.return_value = AsyncMock()

            # Mock logger to capture warnings
            with patch("src.domains.remittances.service.logger") as mock_logger:
                # Act
                await _sync_batch_payment_invoices(
                    db=mock_prisma,
                    org_id=org_id,
                    matched_invoices=mock_matched_invoices,
                    data_service=mock_data_service,
                )

                # Assert
                # Verify all invoices were attempted
                assert mock_data_service.get_invoices.call_count == 3

                # Verify only successful invoices were upserted (2 out of 3)
                assert mock_orchestrator._upsert_invoices.call_count == 2

                # Verify error was logged for failed invoice (exactly one failure)
                warning_calls = mock_logger.warning.call_args_list
                failure_warnings = [
                    call
                    for call in warning_calls
                    if "Xero API error: Invoice not found" in str(call)
                ]
                assert len(failure_warnings) == 1
                warning_call = failure_warnings[0][0][0]
                assert "Failed to sync invoice xero-invoice-2" in warning_call
                assert "Xero API error: Invoice not found" in warning_call

    @pytest.mark.asyncio
    async def test_sync_empty_invoice_responses(
        self,
        mock_prisma: Mock,
        mock_matched_invoices: list,
    ) -> None:
        """Test handling when Xero returns empty responses for invoices."""
        # Arrange
        org_id = "test-org-123"

        # Mock data service returning empty responses
        mock_data_service = AsyncMock()
        mock_data_service.get_invoices.return_value = []  # Empty response

        # Mock SyncOrchestrator
        with patch(
            "src.domains.remittances.service.SyncOrchestrator"
        ) as mock_orchestrator_class:
            mock_orchestrator = Mock()
            mock_orchestrator_class.return_value = mock_orchestrator
            mock_orchestrator._upsert_invoices.return_value = AsyncMock()

            # Act
            await _sync_batch_payment_invoices(
                db=mock_prisma,
                org_id=org_id,
                matched_invoices=mock_matched_invoices,
                data_service=mock_data_service,
            )

            # Assert
            # Verify all invoices were attempted
            assert mock_data_service.get_invoices.call_count == 3

            # Verify no upserts were performed (all responses were empty)
            mock_orchestrator._upsert_invoices.assert_not_called()

    @pytest.mark.asyncio
    async def test_sync_no_matched_invoices(
        self,
        mock_prisma: Mock,
    ) -> None:
        """Test sync with empty invoice list."""
        # Arrange
        org_id = "test-org-123"
        empty_invoices = []

        # Mock data service (should not be called)
        mock_data_service = AsyncMock()

        # Mock SyncOrchestrator
        with patch(
            "src.domains.remittances.service.SyncOrchestrator"
        ) as mock_orchestrator_class:
            mock_orchestrator = Mock()
            mock_orchestrator_class.return_value = mock_orchestrator

            # Act
            await _sync_batch_payment_invoices(
                db=mock_prisma,
                org_id=org_id,
                matched_invoices=empty_invoices,
                data_service=mock_data_service,
            )

            # Assert
            # Verify no API calls were made
            mock_data_service.get_invoices.assert_not_called()

            # Verify orchestrator was still created
            mock_orchestrator_class.assert_called_once_with(mock_prisma)

            # Verify no upserts were performed
            mock_orchestrator._upsert_invoices.assert_not_called()

    @pytest.mark.asyncio
    async def test_sync_orchestrator_upsert_failure(
        self,
        mock_prisma: Mock,
        mock_matched_invoices: list,
        mock_xero_invoice_responses: dict,
    ) -> None:
        """Test handling when orchestrator upsert fails."""
        # Arrange
        org_id = "test-org-123"

        # Mock successful data service
        mock_data_service = AsyncMock()
        mock_data_service.get_invoices.return_value = mock_xero_invoice_responses[
            "xero-invoice-1"
        ]["Invoices"]

        # Mock SyncOrchestrator with failing upsert
        with patch(
            "src.domains.remittances.service.SyncOrchestrator"
        ) as mock_orchestrator_class:
            mock_orchestrator = Mock()
            mock_orchestrator_class.return_value = mock_orchestrator

            # Mock upsert failure for first invoice, success for others
            upsert_side_effects = [
                Exception("Database error: Constraint violation"),  # First call fails
                AsyncMock(),  # Second call succeeds
                AsyncMock(),  # Third call succeeds
            ]
            mock_orchestrator._upsert_invoices.side_effect = upsert_side_effects

            # Mock logger to capture warnings
            with patch("src.domains.remittances.service.logger") as mock_logger:
                # Act
                await _sync_batch_payment_invoices(
                    db=mock_prisma,
                    org_id=org_id,
                    matched_invoices=mock_matched_invoices,
                    data_service=mock_data_service,
                )

                # Assert
                # Verify all invoices were fetched
                assert mock_data_service.get_invoices.call_count == 3

                # Verify all upserts were attempted
                assert mock_orchestrator._upsert_invoices.call_count == 3

                # Verify database error was logged
                assert mock_logger.warning.call_count >= 1
                warning_calls = [
                    call[0][0] for call in mock_logger.warning.call_args_list
                ]
                database_error_logged = any(
                    "Database error: Constraint violation" in call
                    for call in warning_calls
                )
                assert database_error_logged

    @pytest.mark.asyncio
    async def test_sync_with_different_invoice_statuses(
        self,
        mock_prisma: Mock,
    ) -> None:
        """Test sync with invoices having different updated statuses."""
        # Arrange
        org_id = "test-org-123"

        # Mock invoices with different scenarios
        invoice1 = Mock()
        invoice1.invoiceId = "paid-invoice"

        invoice2 = Mock()
        invoice2.invoiceId = "partially-paid-invoice"

        invoice3 = Mock()
        invoice3.invoiceId = "overpaid-invoice"

        mixed_invoices = [invoice1, invoice2, invoice3]

        # Mock responses with different payment statuses
        mock_responses = {
            "paid-invoice": [
                {
                    "InvoiceID": "paid-invoice",
                    "Status": "PAID",
                    "AmountDue": 0.00,
                    "AmountPaid": 100.00,
                    "InvoiceNumber": "INV-PAID",
                    "Type": "ACCREC",
                    "Contact": {
                        "ContactID": "contact-1",
                        "Name": "Customer 1",
                        "ContactStatus": "ACTIVE",
                    },
                    "Date": "/Date(1704067200000+0000)/",
                    "LineAmountTypes": "Exclusive",
                    "SubTotal": 90.91,
                    "TotalTax": 9.09,
                    "Total": 100.00,
                    "AmountCredited": 0.00,
                    "CurrencyCode": "AUD",
                    "LineItems": [],
                }
            ],
            "partially-paid-invoice": [
                {
                    "InvoiceID": "partially-paid-invoice",
                    "Status": "AUTHORISED",  # Still authorized, partial payment
                    "AmountDue": 50.00,
                    "AmountPaid": 50.00,
                    "InvoiceNumber": "INV-PARTIAL",
                    "Type": "ACCREC",
                    "Contact": {
                        "ContactID": "contact-2",
                        "Name": "Customer 2",
                        "ContactStatus": "ACTIVE",
                    },
                    "Date": "/Date(1704067200000+0000)/",
                    "LineAmountTypes": "Exclusive",
                    "SubTotal": 90.91,
                    "TotalTax": 9.09,
                    "Total": 100.00,
                    "AmountCredited": 0.00,
                    "CurrencyCode": "AUD",
                    "LineItems": [],
                }
            ],
            "overpaid-invoice": [
                {
                    "InvoiceID": "overpaid-invoice",
                    "Status": "PAID",
                    "AmountDue": 0.00,
                    "AmountPaid": 100.00,
                    "AmountCredited": 20.00,  # Overpayment credited
                    "InvoiceNumber": "INV-OVER",
                    "Type": "ACCREC",
                    "Contact": {
                        "ContactID": "contact-3",
                        "Name": "Customer 3",
                        "ContactStatus": "ACTIVE",
                    },
                    "Date": "/Date(1704067200000+0000)/",
                    "LineAmountTypes": "Exclusive",
                    "SubTotal": 72.73,
                    "TotalTax": 7.27,
                    "Total": 80.00,
                    "CurrencyCode": "AUD",
                    "LineItems": [],
                }
            ],
        }

        # Mock data service
        mock_data_service = AsyncMock()

        async def get_invoices_side_effect(org_id, filters, invoice_id=None):
            return mock_responses.get(invoice_id, [])

        mock_data_service.get_invoices.side_effect = get_invoices_side_effect

        # Mock SyncOrchestrator
        with patch(
            "src.domains.remittances.service.SyncOrchestrator"
        ) as mock_orchestrator_class:
            mock_orchestrator = Mock()
            mock_orchestrator_class.return_value = mock_orchestrator
            mock_orchestrator._upsert_invoices.return_value = AsyncMock()

            # Act
            await _sync_batch_payment_invoices(
                db=mock_prisma,
                org_id=org_id,
                matched_invoices=mixed_invoices,
                data_service=mock_data_service,
            )

            # Assert
            # Verify all invoices were processed
            assert mock_data_service.get_invoices.call_count == 3
            assert mock_orchestrator._upsert_invoices.call_count == 3

            # Verify the different invoice types were all processed
            upsert_calls = mock_orchestrator._upsert_invoices.call_args_list
            processed_invoices = []
            for call in upsert_calls:
                args, kwargs = call
                invoices_list = args[1]  # Second argument is the invoices list
                if invoices_list:
                    processed_invoices.extend(invoices_list)

            # Verify we processed invoices with different statuses
            invoice_ids = [inv["InvoiceID"] for inv in processed_invoices]
            assert "paid-invoice" in invoice_ids
            assert "partially-paid-invoice" in invoice_ids
            assert "overpaid-invoice" in invoice_ids
