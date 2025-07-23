"""
Tests for remittance approval with file upload functionality.
"""

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, Mock, patch

import pytest
from prisma.enums import RemittanceStatus

from src.domains.remittances.service import approve_remittance


class TestRemittanceApprovalWithUpload:
    """Test suite for remittance approval with attachment upload."""

    @pytest.fixture
    def mock_remittance_with_file(self) -> Mock:
        """Mock remittance with file path."""
        remittance = Mock()
        remittance.id = "test-remittance-123"
        remittance.organizationId = "test-org-123"
        remittance.status = RemittanceStatus.Awaiting_Approval
        remittance.filePath = "test-org-123/2024/01/test-file.pdf"
        remittance.reference = "REF-12345"
        remittance.filename = "test_remittance.pdf"
        remittance.paymentDate = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)

        # Mock remittance lines with matched invoices
        line1 = Mock()
        line1.id = "line-1"
        line1.aiInvoiceId = "ai-invoice-1"
        line1.overrideInvoiceId = None
        line1.aiPaidAmount = Decimal("100.00")
        line1.invoiceNumber = "INV-001"

        line2 = Mock()
        line2.id = "line-2"
        line2.aiInvoiceId = "ai-invoice-2"
        line2.overrideInvoiceId = None
        line2.aiPaidAmount = Decimal("200.00")
        line2.invoiceNumber = "INV-002"

        remittance.lines = [line1, line2]
        return remittance

    @pytest.fixture
    def mock_bank_account(self) -> Mock:
        """Mock default bank account."""
        account = Mock()
        account.id = "bank-account-123"
        account.xeroAccountId = "xero-account-123"
        account.isDefault = True
        return account

    @pytest.fixture
    def mock_matched_invoices(self) -> list:
        """Mock matched invoices from database."""
        invoice1 = Mock()
        invoice1.id = "ai-invoice-1"
        invoice1.invoiceId = "xero-invoice-1"
        invoice1.invoiceNumber = "INV-001"

        invoice2 = Mock()
        invoice2.id = "ai-invoice-2"
        invoice2.invoiceId = "xero-invoice-2"
        invoice2.invoiceNumber = "INV-002"

        return [invoice1, invoice2]

    @pytest.fixture
    def mock_file_content(self) -> bytes:
        """Mock PDF file content."""
        return b"mock pdf content for testing"

    @pytest.mark.asyncio
    async def test_approve_remittance_with_successful_upload(
        self,
        mock_prisma: Mock,
        mock_remittance_with_file: Mock,
        mock_bank_account: Mock,
        mock_matched_invoices: list,
        mock_file_content: bytes,
    ) -> None:
        """Test complete approval flow with successful file upload."""
        # Arrange
        org_id = "test-org-123"
        user_id = "test-user-123"
        remittance_id = "test-remittance-123"

        # Mock database operations
        mock_prisma.remittance.find_unique.return_value = mock_remittance_with_file
        mock_prisma.bankaccount.find_first.return_value = mock_bank_account
        mock_prisma.invoice.find_many.return_value = mock_matched_invoices

        # Mock remittance update
        updated_remittance = Mock()
        mock_prisma.remittance.update.return_value = updated_remittance

        # Mock audit log creation
        mock_prisma.auditlog.create.return_value = Mock()

        # Mock Supabase file download
        with patch("src.domains.remittances.service.supabase") as mock_supabase:
            mock_supabase.storage.from_.return_value.download.return_value = (
                mock_file_content
            )

            # Mock integration factory and data service
            with patch(
                "src.domains.remittances.service.IntegrationFactory"
            ) as mock_factory_class:
                mock_factory = Mock()
                mock_factory_class.return_value = mock_factory

                mock_data_service = AsyncMock()
                mock_factory.get_data_service = AsyncMock(
                    return_value=mock_data_service
                )

                # Mock successful batch payment creation
                from src.domains.external_accounting.base.types import (
                    BatchPaymentResult,
                )

                batch_result = BatchPaymentResult(
                    success=True, batch_id="xero-batch-123", error_message=None
                )
                mock_data_service.create_batch_payment.return_value = batch_result

                # Mock upload_attachment method
                mock_attachment = Mock()
                mock_data_service.upload_attachment.return_value = mock_attachment

                # Mock asyncio.create_task to capture the coroutines
                created_tasks = []
                original_create_task = asyncio.create_task

                def mock_create_task(coro):
                    task = original_create_task(coro)
                    created_tasks.append(task)
                    return task

                with patch("asyncio.create_task", side_effect=mock_create_task):
                    # Mock get_remittance_by_id return
                    with patch(
                        "src.domains.remittances.service.get_remittance_by_id"
                    ) as mock_get_remittance:
                        mock_final_remittance = Mock()
                        mock_get_remittance.return_value = mock_final_remittance

                        # Act
                        result = await approve_remittance(
                            db=mock_prisma,
                            org_id=org_id,
                            user_id=user_id,
                            remittance_id=remittance_id,
                        )

                        # Assert
                        assert result == mock_final_remittance

                        # Verify file was downloaded from Supabase
                        mock_supabase.storage.from_.assert_called_with("remittances")
                        download_call = (
                            mock_supabase.storage.from_.return_value.download
                        )
                        download_call.assert_called_with(
                            "test-org-123/2024/01/test-file.pdf"
                        )

                        # Verify batch payment was created
                        mock_data_service.create_batch_payment.assert_called_once()
                        batch_call_args = (
                            mock_data_service.create_batch_payment.call_args
                        )
                        assert batch_call_args[0][0] == org_id  # org_id parameter
                        batch_data = batch_call_args[0][1]  # BatchPaymentData
                        assert batch_data.account_id == "xero-account-123"
                        assert len(batch_data.payments) == 2

                        # Verify remittance status was updated
                        mock_prisma.remittance.update.assert_called()
                        update_call = mock_prisma.remittance.update.call_args
                        assert update_call[1]["where"] == {"id": remittance_id}
                        update_data = update_call[1]["data"]
                        assert (
                            update_data["status"]
                            == RemittanceStatus.Exported_Unreconciled
                        )
                        assert update_data["xeroBatchId"] == "xero-batch-123"

                        # Verify async tasks were created
                        assert (
                            len(created_tasks) == 2
                        )  # Upload task + invoice sync task

                        # Verify audit log was created for success
                        mock_prisma.auditlog.create.assert_called()

                        # Wait for async tasks to complete for testing
                        for task in created_tasks:
                            if not task.done():
                                await task

                        # After tasks complete, verify upload_attachment was called
                        mock_data_service.upload_attachment.assert_called_once_with(
                            org_id=org_id,
                            entity_id="xero-batch-123",
                            entity_type="BatchPayments",
                            file_data=mock_file_content,
                            filename="Remittance_REF-12345.pdf",
                        )

    @pytest.mark.asyncio
    async def test_approve_remittance_file_download_fails(
        self,
        mock_prisma: Mock,
        mock_remittance_with_file: Mock,
        mock_bank_account: Mock,
        mock_matched_invoices: list,
    ) -> None:
        """Test approval continues when file download fails."""
        # Arrange
        org_id = "test-org-123"
        user_id = "test-user-123"
        remittance_id = "test-remittance-123"

        # Mock database operations
        mock_prisma.remittance.find_unique.return_value = mock_remittance_with_file
        mock_prisma.bankaccount.find_first.return_value = mock_bank_account
        mock_prisma.invoice.find_many.return_value = mock_matched_invoices
        mock_prisma.remittance.update.return_value = Mock()
        mock_prisma.auditlog.create.return_value = Mock()

        # Mock Supabase file download failure
        with patch("src.domains.remittances.service.supabase") as mock_supabase:
            mock_supabase.storage.from_.return_value.download.side_effect = Exception(
                "File not found"
            )

            # Mock integration factory and data service
            with patch(
                "src.domains.remittances.service.IntegrationFactory"
            ) as mock_factory_class:
                mock_factory = Mock()
                mock_factory_class.return_value = mock_factory

                mock_data_service = AsyncMock()
                mock_factory.get_data_service = AsyncMock(
                    return_value=mock_data_service
                )

                # Mock successful batch payment creation
                from src.domains.external_accounting.base.types import (
                    BatchPaymentResult,
                )

                batch_result = BatchPaymentResult(
                    success=True, batch_id="xero-batch-123", error_message=None
                )
                mock_data_service.create_batch_payment.return_value = batch_result

                # Track created tasks
                created_tasks = []
                original_create_task = asyncio.create_task

                def mock_create_task(coro):
                    task = original_create_task(coro)
                    created_tasks.append(task)
                    return task

                with patch("asyncio.create_task", side_effect=mock_create_task):
                    with patch(
                        "src.domains.remittances.service.get_remittance_by_id"
                    ) as mock_get_remittance:
                        mock_final_remittance = Mock()
                        mock_get_remittance.return_value = mock_final_remittance

                        # Act
                        result = await approve_remittance(
                            db=mock_prisma,
                            org_id=org_id,
                            user_id=user_id,
                            remittance_id=remittance_id,
                        )

                        # Assert
                        assert result == mock_final_remittance

                        # Verify batch payment created despite download failure
                        mock_data_service.create_batch_payment.assert_called_once()

                        # Verify remittance status was updated
                        mock_prisma.remittance.update.assert_called()

                        # Verify only one async task created (invoice sync, no upload)
                        assert len(created_tasks) == 1

                        # Verify upload_attachment was NOT called
                        mock_data_service.upload_attachment.assert_not_called()

    @pytest.mark.asyncio
    async def test_approve_remittance_batch_payment_fails(
        self,
        mock_prisma: Mock,
        mock_remittance_with_file: Mock,
        mock_bank_account: Mock,
        mock_matched_invoices: list,
        mock_file_content: bytes,
    ) -> None:
        """Test when batch payment creation fails."""
        # Arrange
        org_id = "test-org-123"
        user_id = "test-user-123"
        remittance_id = "test-remittance-123"

        # Mock database operations
        mock_prisma.remittance.find_unique.return_value = mock_remittance_with_file
        mock_prisma.bankaccount.find_first.return_value = mock_bank_account
        mock_prisma.invoice.find_many.return_value = mock_matched_invoices
        mock_prisma.remittance.update.return_value = Mock()
        mock_prisma.auditlog.create.return_value = Mock()

        # Mock successful file download
        with patch("src.domains.remittances.service.supabase") as mock_supabase:
            mock_supabase.storage.from_.return_value.download.return_value = (
                mock_file_content
            )

            # Mock integration factory and data service
            with patch(
                "src.domains.remittances.service.IntegrationFactory"
            ) as mock_factory_class:
                mock_factory = Mock()
                mock_factory_class.return_value = mock_factory

                mock_data_service = AsyncMock()
                mock_factory.get_data_service = AsyncMock(
                    return_value=mock_data_service
                )

                # Mock failed batch payment creation
                from src.domains.external_accounting.base.types import (
                    BatchPaymentResult,
                )

                batch_result = BatchPaymentResult(
                    success=False,
                    batch_id=None,
                    error_message="Invoice not found in Xero",
                )
                mock_data_service.create_batch_payment.return_value = batch_result

                # Track created tasks
                created_tasks = []
                original_create_task = asyncio.create_task

                def mock_create_task(coro):
                    task = original_create_task(coro)
                    created_tasks.append(task)
                    return task

                with patch("asyncio.create_task", side_effect=mock_create_task):
                    with patch(
                        "src.domains.remittances.service.get_remittance_by_id"
                    ) as mock_get_remittance:
                        mock_final_remittance = Mock()
                        mock_get_remittance.return_value = mock_final_remittance

                        # Act
                        result = await approve_remittance(
                            db=mock_prisma,
                            org_id=org_id,
                            user_id=user_id,
                            remittance_id=remittance_id,
                        )

                        # Assert
                        assert result == mock_final_remittance

                        # Verify batch payment attempt was made
                        mock_data_service.create_batch_payment.assert_called_once()

                        # Verify remittance status was updated to Export_Failed
                        mock_prisma.remittance.update.assert_called()
                        update_call = mock_prisma.remittance.update.call_args
                        update_data = update_call[1]["data"]
                        assert update_data["status"] == RemittanceStatus.Export_Failed
                        assert update_data["xeroBatchId"] is None

                        # Verify no async tasks were created (no upload or sync)
                        assert len(created_tasks) == 0

                        # Verify upload_attachment was NOT called
                        mock_data_service.upload_attachment.assert_not_called()

                        # Verify error audit log was created
                        mock_prisma.auditlog.create.assert_called()
                        audit_calls = mock_prisma.auditlog.create.call_args_list
                        # Should have both start audit and error audit
                        error_message = "Invoice not found in Xero"
                        error_audit = next(
                            call
                            for call in audit_calls
                            if call[1]["data"].get("errorMessage") == error_message
                        )
                        assert error_audit is not None

    @pytest.mark.asyncio
    async def test_approve_remittance_no_file_path(
        self,
        mock_prisma: Mock,
        mock_bank_account: Mock,
        mock_matched_invoices: list,
    ) -> None:
        """Test approval when remittance has no file path."""
        # Arrange
        org_id = "test-org-123"
        user_id = "test-user-123"
        remittance_id = "test-remittance-123"

        # Mock remittance without file path
        remittance_no_file = Mock()
        remittance_no_file.id = remittance_id
        remittance_no_file.organizationId = org_id
        remittance_no_file.status = RemittanceStatus.Awaiting_Approval
        remittance_no_file.filePath = None  # No file path
        remittance_no_file.reference = "REF-12345"
        remittance_no_file.paymentDate = datetime(
            2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc
        )

        # Mock lines
        line1 = Mock()
        line1.aiInvoiceId = "ai-invoice-1"
        line1.overrideInvoiceId = None
        line1.aiPaidAmount = Decimal("100.00")
        remittance_no_file.lines = [line1]

        # Mock database operations
        mock_prisma.remittance.find_unique.return_value = remittance_no_file
        mock_prisma.bankaccount.find_first.return_value = mock_bank_account
        mock_prisma.invoice.find_many.return_value = mock_matched_invoices
        mock_prisma.remittance.update.return_value = Mock()
        mock_prisma.auditlog.create.return_value = Mock()

        # Mock integration factory and data service
        with patch(
            "src.domains.remittances.service.IntegrationFactory"
        ) as mock_factory_class:
            mock_factory = Mock()
            mock_factory_class.return_value = mock_factory

            mock_data_service = AsyncMock()
            mock_factory.get_data_service = AsyncMock(return_value=mock_data_service)

            # Mock successful batch payment creation
            from src.domains.external_accounting.base.types import BatchPaymentResult

            batch_result = BatchPaymentResult(
                success=True, batch_id="xero-batch-123", error_message=None
            )
            mock_data_service.create_batch_payment.return_value = batch_result

            # Track created tasks
            created_tasks = []
            original_create_task = asyncio.create_task

            def mock_create_task(coro):
                task = original_create_task(coro)
                created_tasks.append(task)
                return task

            with patch("asyncio.create_task", side_effect=mock_create_task):
                with patch(
                    "src.domains.remittances.service.get_remittance_by_id"
                ) as mock_get_remittance:
                    mock_final_remittance = Mock()
                    mock_get_remittance.return_value = mock_final_remittance

                    # Act
                    result = await approve_remittance(
                        db=mock_prisma,
                        org_id=org_id,
                        user_id=user_id,
                        remittance_id=remittance_id,
                    )

                    # Assert
                    assert result == mock_final_remittance

                    # Verify batch payment was created
                    mock_data_service.create_batch_payment.assert_called_once()

                    # Verify only invoice sync task was created (no upload task)
                    assert len(created_tasks) == 1

                    # Verify upload_attachment was NOT called
                    mock_data_service.upload_attachment.assert_not_called()

                    # Verify Supabase download was NOT attempted
                    with patch("src.domains.remittances.service.supabase") as mock_sb:
                        mock_sb.storage.from_.return_value.download.assert_not_called()
