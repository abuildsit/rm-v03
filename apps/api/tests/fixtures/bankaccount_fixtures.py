"""
Test fixtures and factories for bank account-related test data.
"""

from datetime import datetime
from typing import Any, Dict
from unittest.mock import Mock

import pytest
from prisma.models import BankAccount


@pytest.fixture
def mock_bank_account() -> Mock:
    """Mock BankAccount object for testing."""
    account = Mock(spec=BankAccount)
    account.id = "test-bank-account-123"
    account.organizationId = "test-org-id-123"
    account.xeroAccountId = "12345678-1234-1234-1234-123456789012"
    account.xeroName = "Business Bank Account"
    account.xeroCode = "090"
    account.type = "BANK"
    account.status = "ACTIVE"
    account.isDefault = False
    account.currencyCode = "AUD"
    account.enablePaymentsToAccount = True
    account.bankAccountNumber = "123456789"
    account.createdAt = datetime(2024, 1, 15, 9, 0, 0)
    account.updatedAt = datetime(2024, 1, 15, 9, 0, 0)
    return account


@pytest.fixture
def mock_bank_account_default() -> Mock:
    """Mock BankAccount object with is_default=True for testing."""
    account = Mock(spec=BankAccount)
    account.id = "test-bank-account-default-456"
    account.organizationId = "test-org-id-123"
    account.xeroAccountId = "87654321-4321-4321-4321-210987654321"
    account.xeroName = "Default Business Account"
    account.xeroCode = "091"
    account.type = "BANK"
    account.status = "ACTIVE"
    account.isDefault = True
    account.currencyCode = "AUD"
    account.enablePaymentsToAccount = True
    account.bankAccountNumber = "987654321"
    account.createdAt = datetime(2024, 1, 10, 9, 0, 0)
    account.updatedAt = datetime(2024, 1, 10, 9, 0, 0)
    return account


@pytest.fixture
def mock_bank_account_disabled() -> Mock:
    """Mock BankAccount object with payments disabled for testing."""
    account = Mock(spec=BankAccount)
    account.id = "test-bank-account-disabled-789"
    account.organizationId = "test-org-id-123"
    account.xeroAccountId = "11111111-1111-1111-1111-111111111111"
    account.xeroName = "Savings Account"
    account.xeroCode = "092"
    account.type = "BANK"
    account.status = "ACTIVE"
    account.isDefault = False
    account.currencyCode = "AUD"
    account.enablePaymentsToAccount = False
    account.bankAccountNumber = "111111111"
    account.createdAt = datetime(2024, 1, 5, 9, 0, 0)
    account.updatedAt = datetime(2024, 1, 5, 9, 0, 0)
    return account


@pytest.fixture
def mock_bank_accounts_list() -> list[Mock]:
    """Mock list of BankAccount objects for testing."""
    account1 = Mock(spec=BankAccount)
    account1.id = "test-bank-account-123"
    account1.organizationId = "test-org-id-123"
    account1.xeroAccountId = "12345678-1234-1234-1234-123456789012"
    account1.xeroName = "Business Bank Account"
    account1.xeroCode = "090"
    account1.type = "BANK"
    account1.status = "ACTIVE"
    account1.isDefault = False
    account1.currencyCode = "AUD"
    account1.enablePaymentsToAccount = True

    account2 = Mock(spec=BankAccount)
    account2.id = "test-bank-account-456"
    account2.organizationId = "test-org-id-123"
    account2.xeroAccountId = "87654321-4321-4321-4321-210987654321"
    account2.xeroName = "Default Business Account"
    account2.xeroCode = "091"
    account2.type = "BANK"
    account2.status = "ACTIVE"
    account2.isDefault = True
    account2.currencyCode = "AUD"
    account2.enablePaymentsToAccount = True

    return [account1, account2]


@pytest.fixture
def bank_account_update_data() -> Dict[str, Any]:
    """Valid bank account update data for testing."""
    return {
        "accountId": "test-bank-account-123",
        "enablePaymentsToAccount": True,
        "isDefault": False,
    }


@pytest.fixture
def bank_account_save_request_data() -> Dict[str, Any]:
    """Valid bank account save request data for testing."""
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


class BankAccountTestData:
    """Helper class for generating consistent bank account test data."""

    @staticmethod
    def account_ids() -> Dict[str, str]:
        """Standard test account IDs."""
        return {
            "primary": "test-bank-account-123",
            "secondary": "test-bank-account-456",
            "disabled": "test-bank-account-disabled-789",
            "nonexistent": "nonexistent-account-id",
        }

    @staticmethod
    def organization_ids() -> Dict[str, str]:
        """Standard test organization IDs."""
        return {
            "primary": "test-org-id-123",
            "secondary": "test-org-id-456",
            "different": "different-org-id-789",
        }

    @staticmethod
    def xero_account_ids() -> Dict[str, str]:
        """Standard test Xero account IDs."""
        return {
            "primary": "12345678-1234-1234-1234-123456789012",
            "secondary": "87654321-4321-4321-4321-210987654321",
            "tertiary": "11111111-1111-1111-1111-111111111111",
        }

    @staticmethod
    def account_types() -> list[str]:
        """Available account types."""
        return ["BANK", "CREDITCARD", "PAYPAL"]

    @staticmethod
    def account_statuses() -> list[str]:
        """Available account statuses."""
        return ["ACTIVE", "ARCHIVED", "DELETED"]

    @staticmethod
    def currency_codes() -> list[str]:
        """Available currency codes."""
        return ["AUD", "USD", "EUR", "GBP", "NZD"]
