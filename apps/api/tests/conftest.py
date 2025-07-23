"""
Global pytest configuration and fixtures for the RemitMatch API test suite.
"""

import asyncio
import os
from typing import Any, Dict, Generator
from unittest.mock import AsyncMock, Mock

import jwt
import pytest
from fastapi.testclient import TestClient
from prisma.enums import InvoiceStatus, MemberStatus, OrganizationRole
from prisma.models import AuthLink, Invoice, OrganizationMember, Profile

from prisma import Prisma
from src.main import app

# Import fixtures from fixture modules
from tests.fixtures.batch_payment_fixtures import *  # noqa: F403, F401
from tests.fixtures.organization_fixtures import *  # noqa: F403, F401
from tests.fixtures.remittance_fixtures import *  # noqa: F403, F401
from tests.fixtures.xero_fixtures import *  # noqa: F403, F401

# Set test environment variables
os.environ["JWT_SECRET"] = "test-secret-key-for-testing-only-32-chars"


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_prisma() -> Mock:
    """
    Mock Prisma client for unit tests that don't need real database.
    """
    mock_db = Mock(spec=Prisma)
    # Make async methods return AsyncMock
    mock_db.authlink.find_first = AsyncMock()
    mock_db.organizationmember.find_first = AsyncMock()
    mock_db.organizationmember.find_many = AsyncMock()
    mock_db.organizationmember.create = AsyncMock()
    mock_db.organization.create = AsyncMock()
    mock_db.profile.update = AsyncMock()
    mock_db.profile.find_unique = AsyncMock()
    mock_db.invoice.find_many = AsyncMock()
    mock_db.invoice.count = AsyncMock()

    # Xero integration mocks
    mock_db.xeroconnection.find_first = AsyncMock()
    mock_db.xeroconnection.create = AsyncMock()
    mock_db.xeroconnection.update = AsyncMock()
    mock_db.xeroconnection.delete = AsyncMock()

    return mock_db


@pytest.fixture
def test_jwt_secret() -> str:
    """JWT secret for generating test tokens."""
    return "test-secret-key-for-testing-only-32-chars"


@pytest.fixture
def valid_jwt_payload() -> Dict[str, Any]:
    """Valid JWT payload for testing."""
    return {
        "sub": "test-user-id-123",
        "email": "test@example.com",
        "aud": "authenticated",
        "iss": "supabase",
    }


@pytest.fixture
def valid_jwt_token(test_jwt_secret: str, valid_jwt_payload: Dict[str, Any]) -> str:
    """Generate a valid JWT token for testing."""
    return jwt.encode(valid_jwt_payload, test_jwt_secret, algorithm="HS256")


@pytest.fixture
def invalid_jwt_token(test_jwt_secret: str) -> str:
    """Generate an invalid JWT token for testing."""
    return jwt.encode({"invalid": "payload"}, "wrong-secret", algorithm="HS256")


@pytest.fixture
def auth_headers(valid_jwt_token: str) -> Dict[str, str]:
    """Generate authentication headers with valid JWT token."""
    return {"Authorization": f"Bearer {valid_jwt_token}"}


@pytest.fixture
def test_client() -> TestClient:
    """FastAPI test client for API endpoint testing."""
    return TestClient(app)


@pytest.fixture
def client() -> TestClient:
    """Alias for test_client to match existing test patterns."""
    return TestClient(app)


# Test data fixtures for consistent test scenarios
@pytest.fixture
def test_organization_id() -> str:
    """Standard test organization ID."""
    return "42f929b1-8fdb-45b1-a7cf-34fae2314561"


@pytest.fixture
def test_profile_id() -> str:
    """Standard test profile ID."""
    return "test-profile-id-123"


@pytest.fixture
def test_auth_id() -> str:
    """Standard test auth ID."""
    return "test-user-id-123"


@pytest.fixture
def test_invoice_id() -> str:
    """Standard test invoice ID."""
    return "test-invoice-id-123"


# Mock data fixtures
@pytest.fixture
def mock_profile() -> Mock:
    """Mock Profile object for testing."""
    profile = Mock(spec=Profile)
    profile.id = "test-profile-id-123"
    profile.email = "test@example.com"
    profile.displayName = "Test User"
    profile.lastAccessedOrgId = "42f929b1-8fdb-45b1-a7cf-34fae2314561"
    return profile


@pytest.fixture
def mock_auth_link() -> Mock:
    """Mock AuthLink object for testing."""
    auth_link = Mock(spec=AuthLink)
    auth_link.id = "test-auth-link-id"
    auth_link.authId = "test-user-id-123"
    auth_link.profileId = "test-profile-id-123"
    auth_link.provider = "supabase"
    auth_link.providerUserId = "test-user-id-123"
    auth_link.profile = None  # Default to no profile
    return auth_link


@pytest.fixture
def mock_auth_link_with_profile(mock_auth_link: Mock, mock_profile: Mock) -> Mock:
    """Mock AuthLink with associated Profile."""
    mock_auth_link.profile = mock_profile
    return mock_auth_link


@pytest.fixture
def mock_organization_member() -> Mock:
    """Mock OrganizationMember object for testing."""
    member = Mock(spec=OrganizationMember)
    member.id = "test-member-id"
    member.profileId = "test-profile-id-123"
    member.organizationId = "42f929b1-8fdb-45b1-a7cf-34fae2314561"
    member.role = OrganizationRole.admin
    member.status = MemberStatus.active
    return member


@pytest.fixture
def mock_organization_member_owner() -> Mock:
    """Mock OrganizationMember with owner role for testing."""
    member = Mock(spec=OrganizationMember)
    member.id = "test-owner-member-id"
    member.profileId = "test-profile-id-123"
    member.organizationId = "42f929b1-8fdb-45b1-a7cf-34fae2314561"
    member.role = OrganizationRole.owner
    member.status = MemberStatus.active
    return member


@pytest.fixture
def mock_organization_member_admin() -> Mock:
    """Mock OrganizationMember with admin role for testing."""
    member = Mock(spec=OrganizationMember)
    member.id = "test-admin-member-id"
    member.profileId = "test-profile-id-123"
    member.organizationId = "42f929b1-8fdb-45b1-a7cf-34fae2314561"
    member.role = OrganizationRole.admin
    member.status = MemberStatus.active
    return member


@pytest.fixture
def mock_organization_member_auditor() -> Mock:
    """Mock OrganizationMember with auditor role for testing."""
    member = Mock(spec=OrganizationMember)
    member.id = "test-auditor-member-id"
    member.profileId = "test-profile-id-123"
    member.organizationId = "42f929b1-8fdb-45b1-a7cf-34fae2314561"
    member.role = OrganizationRole.auditor
    member.status = MemberStatus.active
    return member


@pytest.fixture
def mock_organization_member_user() -> Mock:
    """Mock OrganizationMember with user role for testing."""
    member = Mock(spec=OrganizationMember)
    member.id = "test-user-member-id"
    member.profileId = "test-profile-id-123"
    member.organizationId = "42f929b1-8fdb-45b1-a7cf-34fae2314561"
    member.role = OrganizationRole.user
    member.status = MemberStatus.active
    return member


@pytest.fixture
def mock_invoice() -> Mock:
    """Mock Invoice object for testing."""
    from datetime import date, datetime
    from decimal import Decimal

    invoice = Mock(spec=Invoice)
    # Set all fields that InvoiceResponse.from_prisma() expects
    invoice.id = "test-invoice-id-123"
    invoice.organizationId = "42f929b1-8fdb-45b1-a7cf-34fae2314561"
    invoice.invoiceId = "inv-001"
    invoice.invoiceNumber = "INV-001"
    invoice.contactName = "Test Contact"
    invoice.contactId = "contact-123"
    invoice.invoiceDate = date(2024, 1, 15)
    invoice.dueDate = date(2024, 2, 15)
    invoice.status = InvoiceStatus.AUTHORISED
    invoice.lineAmountTypes = "Exclusive"
    invoice.subTotal = Decimal("100.00")
    invoice.totalTax = Decimal("10.00")
    invoice.total = Decimal("110.00")
    invoice.amountDue = Decimal("110.00")
    invoice.amountPaid = Decimal("0.00")
    invoice.amountCredited = Decimal("0.00")
    invoice.currencyCode = "AUD"
    invoice.reference = "Test Reference"
    invoice.brandId = None
    invoice.hasErrors = False
    invoice.isDiscounted = False
    invoice.hasAttachments = False
    invoice.sentToContact = True
    invoice.lastSyncedAt = datetime(2024, 1, 15, 10, 0, 0)
    invoice.xeroUpdatedDateUtc = None
    invoice.createdAt = datetime(2024, 1, 15, 9, 0, 0)
    invoice.updatedAt = datetime(2024, 1, 15, 9, 0, 0)
    return invoice


@pytest.fixture
def mock_invoice_list() -> list:
    """List of mock Invoice objects for pagination testing."""
    from datetime import date, datetime
    from decimal import Decimal

    invoices = []
    for i in range(3):
        invoice = Mock(spec=Invoice)
        # Set all fields that InvoiceResponse.from_prisma() expects
        invoice.id = f"test-invoice-id-{i}"
        invoice.organizationId = "42f929b1-8fdb-45b1-a7cf-34fae2314561"
        invoice.invoiceId = f"inv-00{i + 1}"
        invoice.invoiceNumber = f"INV-00{i + 1}"
        invoice.contactName = f"Test Contact {i + 1}"
        invoice.contactId = f"contact-{i + 1}"
        invoice.invoiceDate = date(2024, 1, 15 + i)
        invoice.dueDate = date(2024, 2, 15 + i)
        invoice.status = InvoiceStatus.AUTHORISED
        invoice.lineAmountTypes = "Exclusive"
        invoice.subTotal = Decimal(f"{100 + i * 10}.00")
        invoice.totalTax = Decimal(f"{10 + i}.00")
        invoice.total = Decimal(f"{110 + i * 11}.00")
        invoice.amountDue = Decimal(f"{110 + i * 11}.00")
        invoice.amountPaid = Decimal("0.00")
        invoice.amountCredited = Decimal("0.00")
        invoice.currencyCode = "AUD"
        invoice.reference = f"Test Reference {i + 1}"
        invoice.brandId = None
        invoice.hasErrors = False
        invoice.isDiscounted = False
        invoice.hasAttachments = False
        invoice.sentToContact = True
        invoice.lastSyncedAt = datetime(2024, 1, 15 + i, 10, 0, 0)
        invoice.xeroUpdatedDateUtc = None
        invoice.createdAt = datetime(2024, 1, 15 + i, 9, 0, 0)
        invoice.updatedAt = datetime(2024, 1, 15 + i, 9, 0, 0)
        invoices.append(invoice)
    return invoices
