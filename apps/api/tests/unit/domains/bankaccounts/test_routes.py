"""
Tests for bank accounts routes in src/domains/bankaccounts/routes.py

Focused tests for route logic, with permission system tested separately.
"""

from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
from prisma.models import OrganizationMember

from src.domains.bankaccounts.models import BankAccountResponse


class TestGetBankAccountsRoute:
    """Test GET /bankaccounts/{org_id} endpoint functionality."""

    @pytest.fixture
    def mock_membership(self) -> Mock:
        """Mock OrganizationMember for authenticated user with permission."""
        membership = Mock(spec=OrganizationMember)
        membership.id = "test-membership-id-123"
        membership.organizationId = "test-org-id-123"
        membership.role = "admin"
        return membership

    @pytest.fixture
    def mock_bank_account_responses(self) -> list:
        """Mock list of BankAccountResponse objects."""
        return [
            BankAccountResponse(
                id="test-bank-account-123",
                code="090",
                name="Business Bank Account",
                type="BANK",
                currencyCode="AUD",
                enablePaymentsToAccount=True,
                isDefault=False,
                status="ACTIVE",
            ),
            BankAccountResponse(
                id="test-bank-account-456",
                code="091",
                name="Default Business Account",
                type="BANK",
                currencyCode="AUD",
                enablePaymentsToAccount=True,
                isDefault=True,
                status="ACTIVE",
            ),
        ]

    @pytest.mark.asyncio
    async def test_get_bank_accounts_success(
        self,
        mock_membership: Mock,
        mock_bank_account_responses: list,
    ) -> None:
        """Test successful retrieval of bank accounts."""
        from src.domains.bankaccounts.routes import get_bank_accounts

        org_id = str(uuid4())

        # Mock dependencies
        with patch(
            "src.domains.bankaccounts.routes.get_bank_accounts_by_organization"
        ) as mock_get_accounts:
            mock_db = Mock()
            mock_get_accounts.return_value = mock_bank_account_responses

            # Act
            result = await get_bank_accounts(
                org_id=org_id, membership=mock_membership, db=mock_db
            )

            # Assert
            assert result == mock_bank_account_responses
            assert len(result) == 2

            # Verify service was called correctly
            mock_get_accounts.assert_called_once_with(org_id, mock_db)

    @pytest.mark.asyncio
    async def test_get_bank_accounts_empty(self, mock_membership: Mock) -> None:
        """Test empty list when no accounts exist."""
        from src.domains.bankaccounts.routes import get_bank_accounts

        org_id = str(uuid4())

        # Mock dependencies
        with patch(
            "src.domains.bankaccounts.routes.get_bank_accounts_by_organization"
        ) as mock_get_accounts:
            mock_db = Mock()
            mock_get_accounts.return_value = []

            # Act
            result = await get_bank_accounts(
                org_id=org_id, membership=mock_membership, db=mock_db
            )

            # Assert
            assert result == []
            assert len(result) == 0

    @pytest.mark.asyncio
    async def test_get_bank_accounts_response_structure(
        self, mock_membership: Mock, mock_bank_account_responses: list
    ) -> None:
        """Test route returns correct response structure."""
        from src.domains.bankaccounts.routes import get_bank_accounts

        org_id = str(uuid4())

        # Mock dependencies
        with patch(
            "src.domains.bankaccounts.routes.get_bank_accounts_by_organization"
        ) as mock_get_accounts:
            mock_db = Mock()
            mock_get_accounts.return_value = mock_bank_account_responses

            # Act
            result = await get_bank_accounts(
                org_id=org_id, membership=mock_membership, db=mock_db
            )

            # Assert response structure
            assert isinstance(result, list)
            assert len(result) == 2

            # Verify first account structure
            first_account = result[0]
            assert hasattr(first_account, "id")
            assert hasattr(first_account, "code")
            assert hasattr(first_account, "name")
            assert hasattr(first_account, "type")
            assert hasattr(first_account, "currencyCode")
            assert hasattr(first_account, "enablePaymentsToAccount")
            assert hasattr(first_account, "isDefault")
            assert hasattr(first_account, "status")


class TestUpdateBankAccountsRoute:
    """Test POST /bankaccounts/{org_id} endpoint functionality."""

    @pytest.fixture
    def mock_admin_membership(self) -> Mock:
        """Mock OrganizationMember with admin role."""
        membership = Mock(spec=OrganizationMember)
        membership.id = "membership-123"
        membership.role = "admin"
        membership.organizationId = "test-org-id-123"
        return membership

    @pytest.fixture
    def valid_update_request(self) -> dict:
        """Valid bank account update request data."""
        return {
            "organizationId": "test-org-id-123",
            "accounts": [
                {
                    "accountId": "test-bank-account-123",
                    "enablePaymentsToAccount": True,
                    "isDefault": False,
                },
                {
                    "accountId": "test-bank-account-456",
                    "enablePaymentsToAccount": True,
                    "isDefault": True,
                },
            ],
        }

    @pytest.fixture
    def mock_update_response(self) -> dict:
        """Mock update response."""
        from src.domains.bankaccounts.models import (
            BankAccountSaveResponse,
            BankAccountUpdate,
        )

        return BankAccountSaveResponse(
            success=True,
            message="Bank accounts updated successfully",
            savedAccounts=2,
            accounts=[
                BankAccountUpdate(
                    accountId="test-bank-account-123",
                    enablePaymentsToAccount=True,
                    isDefault=False,
                ),
                BankAccountUpdate(
                    accountId="test-bank-account-456",
                    enablePaymentsToAccount=True,
                    isDefault=True,
                ),
            ],
        )

    @pytest.mark.asyncio
    async def test_update_bank_accounts_success(
        self,
        mock_admin_membership: Mock,
        valid_update_request: dict,
        mock_update_response: dict,
    ) -> None:
        """Test successful bank account update."""
        from src.domains.bankaccounts.routes import update_bank_accounts

        org_id = str(uuid4())

        # Mock dependencies
        with patch(
            "src.domains.bankaccounts.routes.update_bank_accounts_by_organization"
        ) as mock_update_service:
            mock_db = Mock()
            mock_update_service.return_value = mock_update_response

            # Act
            result = await update_bank_accounts(
                org_id=org_id,
                request=valid_update_request,
                membership=mock_admin_membership,
                db=mock_db,
            )

            # Assert
            assert result == mock_update_response
            assert result.success is True
            assert result.savedAccounts == 2

            # Verify service was called correctly
            mock_update_service.assert_called_once_with(
                org_id, valid_update_request, mock_db
            )

    @pytest.mark.asyncio
    async def test_update_bank_accounts_service_error(
        self,
        mock_admin_membership: Mock,
        valid_update_request: dict,
    ) -> None:
        """Test handling of service errors."""
        from fastapi import HTTPException

        from src.domains.bankaccounts.routes import update_bank_accounts

        org_id = str(uuid4())

        # Mock dependencies
        with patch(
            "src.domains.bankaccounts.routes.update_bank_accounts_by_organization"
        ) as mock_update_service:
            mock_db = Mock()
            mock_update_service.side_effect = HTTPException(
                status_code=400, detail="Invalid account ID"
            )

            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                await update_bank_accounts(
                    org_id=org_id,
                    request=valid_update_request,
                    membership=mock_admin_membership,
                    db=mock_db,
                )

            assert exc_info.value.status_code == 400
            assert "Invalid account ID" in exc_info.value.detail
