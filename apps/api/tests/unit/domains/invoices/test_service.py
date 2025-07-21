"""
Tests for invoice service functions in src/domains/invoices/service.py

Tests the core invoice retrieval and filtering functionality.
"""

from datetime import date, datetime
from unittest.mock import Mock

import pytest
from prisma.enums import InvoiceStatus

from src.domains.invoices.service import get_invoices_by_organization


class TestGetInvoicesByOrganization:
    """Test invoice retrieval with various filters and pagination."""

    @pytest.mark.asyncio
    async def test_basic_invoice_retrieval_no_filters(
        self, mock_prisma: Mock, mock_invoice_list: list, test_organization_id: str
    ):
        """Test basic invoice retrieval without any filters."""
        # Mock database responses
        mock_prisma.invoice.find_many.return_value = mock_invoice_list
        mock_prisma.invoice.count.return_value = 3

        result = await get_invoices_by_organization(
            organization_id=test_organization_id, db=mock_prisma, page=1, limit=10
        )

        # Verify response structure
        assert len(result.invoices) == 3
        assert result.pagination.page == 1
        assert result.pagination.limit == 10
        assert result.pagination.total == 3
        assert result.pagination.pages == 1
        assert result.pagination.has_next is False
        assert result.pagination.has_prev is False

        # Verify database calls
        mock_prisma.invoice.find_many.assert_called_once()
        mock_prisma.invoice.count.assert_called_once()

        # Verify where clause
        find_many_call = mock_prisma.invoice.find_many.call_args
        where_clause = find_many_call[1]["where"]
        assert where_clause["organizationId"] == test_organization_id

    @pytest.mark.asyncio
    async def test_invoice_status_filtering(
        self, mock_prisma: Mock, mock_invoice_list: list, test_organization_id: str
    ):
        """Test filtering invoices by status."""
        mock_prisma.invoice.find_many.return_value = mock_invoice_list
        mock_prisma.invoice.count.return_value = 3

        await get_invoices_by_organization(
            organization_id=test_organization_id,
            db=mock_prisma,
            status=InvoiceStatus.AUTHORISED,
        )

        # Verify status filter was applied
        find_many_call = mock_prisma.invoice.find_many.call_args
        where_clause = find_many_call[1]["where"]
        assert where_clause["status"] == InvoiceStatus.AUTHORISED

    @pytest.mark.asyncio
    async def test_date_range_filtering(
        self, mock_prisma: Mock, mock_invoice_list: list, test_organization_id: str
    ):
        """Test filtering invoices by date range."""
        mock_prisma.invoice.find_many.return_value = mock_invoice_list
        mock_prisma.invoice.count.return_value = 3

        date_from = date(2024, 1, 1)
        date_to = date(2024, 1, 31)

        await get_invoices_by_organization(
            organization_id=test_organization_id,
            db=mock_prisma,
            date_from=date_from,
            date_to=date_to,
        )

        # Verify date filters were applied
        find_many_call = mock_prisma.invoice.find_many.call_args
        where_clause = find_many_call[1]["where"]
        assert where_clause["invoiceDate"]["gte"] == datetime.combine(
            date_from, datetime.min.time()
        )
        assert where_clause["invoiceDate"]["lte"] == datetime.combine(
            date_to, datetime.max.time()
        )

    @pytest.mark.asyncio
    async def test_contact_id_filtering(
        self, mock_prisma: Mock, mock_invoice_list: list, test_organization_id: str
    ):
        """Test filtering invoices by contact ID."""
        mock_prisma.invoice.find_many.return_value = mock_invoice_list
        mock_prisma.invoice.count.return_value = 3

        contact_id = "contact-123"

        await get_invoices_by_organization(
            organization_id=test_organization_id, db=mock_prisma, contact_id=contact_id
        )

        # Verify contact filter was applied
        find_many_call = mock_prisma.invoice.find_many.call_args
        where_clause = find_many_call[1]["where"]
        assert where_clause["contactId"] == contact_id

    @pytest.mark.asyncio
    async def test_search_functionality(
        self, mock_prisma: Mock, mock_invoice_list: list, test_organization_id: str
    ):
        """Test text search across multiple fields."""
        mock_prisma.invoice.find_many.return_value = mock_invoice_list
        mock_prisma.invoice.count.return_value = 3

        search_term = "Test"

        await get_invoices_by_organization(
            organization_id=test_organization_id, db=mock_prisma, search=search_term
        )

        # Verify search filter was applied with OR conditions
        find_many_call = mock_prisma.invoice.find_many.call_args
        where_clause = find_many_call[1]["where"]
        or_conditions = where_clause["OR"]

        assert len(or_conditions) == 3
        assert or_conditions[0]["invoiceNumber"]["contains"] == search_term
        assert or_conditions[1]["contactName"]["contains"] == search_term
        assert or_conditions[2]["reference"]["contains"] == search_term

        # Verify case insensitive search
        for condition in or_conditions:
            field_condition = list(condition.values())[0]
            assert field_condition["mode"] == "insensitive"

    @pytest.mark.asyncio
    async def test_modified_since_filtering(
        self, mock_prisma: Mock, mock_invoice_list: list, test_organization_id: str
    ):
        """Test filtering invoices modified since a specific date."""
        mock_prisma.invoice.find_many.return_value = mock_invoice_list
        mock_prisma.invoice.count.return_value = 3

        modified_since = datetime(2024, 1, 15, 10, 0, 0)

        await get_invoices_by_organization(
            organization_id=test_organization_id,
            db=mock_prisma,
            modified_since=modified_since,
        )

        # Verify modified_since filter was applied
        find_many_call = mock_prisma.invoice.find_many.call_args
        where_clause = find_many_call[1]["where"]
        assert where_clause["updatedAt"]["gte"] == modified_since

    @pytest.mark.asyncio
    async def test_pagination_parameters(
        self, mock_prisma: Mock, mock_invoice_list: list, test_organization_id: str
    ):
        """Test pagination skip/take parameters."""
        mock_prisma.invoice.find_many.return_value = mock_invoice_list
        mock_prisma.invoice.count.return_value = 25

        page = 2
        limit = 10

        result = await get_invoices_by_organization(
            organization_id=test_organization_id, db=mock_prisma, page=page, limit=limit
        )

        # Verify pagination parameters
        find_many_call = mock_prisma.invoice.find_many.call_args
        assert find_many_call[1]["skip"] == 10  # (page - 1) * limit
        assert find_many_call[1]["take"] == 10
        assert find_many_call[1]["order"] == {"createdAt": "desc"}

        # Verify pagination metadata
        assert result.pagination.page == 2
        assert result.pagination.limit == 10
        assert result.pagination.total == 25
        assert result.pagination.pages == 3
        assert result.pagination.has_next is True
        assert result.pagination.has_prev is True

    @pytest.mark.asyncio
    async def test_combined_filters(
        self, mock_prisma: Mock, mock_invoice_list: list, test_organization_id: str
    ):
        """Test multiple filters applied together."""
        mock_prisma.invoice.find_many.return_value = mock_invoice_list
        mock_prisma.invoice.count.return_value = 3

        await get_invoices_by_organization(
            organization_id=test_organization_id,
            db=mock_prisma,
            status=InvoiceStatus.AUTHORISED,
            date_from=date(2024, 1, 1),
            contact_id="contact-123",
            search="Test",
        )

        # Verify all filters were applied
        find_many_call = mock_prisma.invoice.find_many.call_args
        where_clause = find_many_call[1]["where"]

        assert where_clause["organizationId"] == test_organization_id
        assert where_clause["status"] == InvoiceStatus.AUTHORISED
        assert where_clause["invoiceDate"]["gte"] == datetime.combine(
            date(2024, 1, 1), datetime.min.time()
        )
        assert where_clause["contactId"] == "contact-123"
        assert "OR" in where_clause  # Search conditions

    @pytest.mark.asyncio
    async def test_empty_result_handling(
        self, mock_prisma: Mock, test_organization_id: str
    ):
        """Test handling of empty result set."""
        mock_prisma.invoice.find_many.return_value = []
        mock_prisma.invoice.count.return_value = 0

        result = await get_invoices_by_organization(
            organization_id=test_organization_id, db=mock_prisma
        )

        assert len(result.invoices) == 0
        assert result.pagination.total == 0
        assert result.pagination.pages == 1  # Always at least 1 page
        assert result.pagination.has_next is False
        assert result.pagination.has_prev is False
