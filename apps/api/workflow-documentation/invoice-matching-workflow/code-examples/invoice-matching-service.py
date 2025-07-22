"""
RemitMatch Invoice Matching Service - Complete Implementation
============================================================

This file demonstrates the complete invoice matching workflow used in RemitMatch
for correlating payment data against invoice records using a three-pass matching strategy.
"""

import asyncio
import logging
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from pydantic import BaseModel, Field


class MatchingPassType(str, Enum):
    """Types of matching passes"""

    EXACT = "exact"
    RELAXED = "relaxed"
    NUMERIC = "numeric"


class InvoiceMatchResult(BaseModel):
    """Result of matching a single payment line"""

    line_id: UUID
    line_invoice_number: str
    matched_invoice_id: Optional[UUID] = None
    matched_invoice_number: Optional[str] = None
    match_type: Optional[MatchingPassType] = None
    confidence: Decimal = Field(default=Decimal("0"), ge=0, le=1)


class InvoiceMatchingSummary(BaseModel):
    """Summary statistics for matching operation"""

    total_lines: int
    matched_count: int
    unmatched_count: int
    match_percentage: Decimal
    all_matched: bool

    # Pass-specific statistics
    exact_matches: int = 0
    relaxed_matches: int = 0
    numeric_matches: int = 0

    # Performance metrics
    processing_time_ms: int = 0


class InvoiceMatchingResult(BaseModel):
    """Complete matching operation result"""

    summary: InvoiceMatchingSummary
    matches: List[InvoiceMatchResult]
    unmatched_lines: List[Dict[str, Any]]


class InvoiceMatchingService:
    """
    Service for matching payment data against invoice records using progressive normalization.

    This service implements a three-pass matching strategy:
    1. Exact match: Case-insensitive with whitespace normalization
    2. Relaxed match: Remove all non-alphanumeric characters
    3. Numeric match: Extract and match digits only

    The service is optimized for performance using O(1) dictionary lookups
    and early termination when all matches are found.
    """

    def __init__(self, database_client):
        self.db = database_client
        self.logger = logging.getLogger(__name__)

        # Performance configuration
        self.batch_size = 1000
        self.max_invoice_cache_size = 10000

    async def match_remittance_payments(
        self, remittance_id: UUID, organization_id: UUID, org_context: Dict[str, Any]
    ) -> InvoiceMatchingResult:
        """
        Main matching method that orchestrates the three-pass matching strategy.

        Args:
            remittance_id: ID of remittance containing payment lines
            organization_id: Organization ID for data isolation
            org_context: Organization context for logging/audit

        Returns:
            Complete matching result with statistics and individual match details
        """
        start_time = asyncio.get_event_loop().time()

        try:
            # Step 1: Fetch input data
            self.logger.info(
                f"Starting invoice matching for remittance {remittance_id}"
            )

            remittance_lines = await self._fetch_remittance_lines(remittance_id)
            if not remittance_lines:
                return self._create_empty_result()

            invoices = await self._fetch_organization_invoices(organization_id)
            if not invoices:
                return self._create_no_invoices_result(remittance_lines)

            self.logger.info(
                f"Processing {len(remittance_lines)} payment lines against {len(invoices)} invoices"
            )

            # Step 2: Execute three-pass matching
            all_matched, unmatched_lines = await self._execute_three_pass_matching(
                remittance_lines, invoices
            )

            # Step 3: Update database with matches
            if all_matched:
                await self._update_matched_lines_in_db(all_matched, org_context)

            # Step 4: Calculate performance metrics
            processing_time = int((asyncio.get_event_loop().time() - start_time) * 1000)

            # Step 5: Compile results
            result = self._compile_matching_result(
                all_matched, unmatched_lines, remittance_lines, processing_time
            )

            self.logger.info(
                f"Matching completed: {result.summary.matched_count}/{result.summary.total_lines} "
                f"matched in {processing_time}ms"
            )

            return result

        except Exception as e:
            self.logger.error(f"Invoice matching failed: {str(e)}")
            raise InvoiceMatchingError(
                f"Matching failed for remittance {remittance_id}: {str(e)}"
            )

    async def _execute_three_pass_matching(
        self, remittance_lines: List[Dict[str, Any]], invoices: List[Dict[str, Any]]
    ) -> Tuple[List[InvoiceMatchResult], List[Dict[str, Any]]]:
        """Execute the three-pass matching strategy"""

        all_matched = []
        unmatched_lines = remittance_lines.copy()

        # Define normalization strategies
        normalizers = [
            (self._exact_normalize, MatchingPassType.EXACT),
            (self._relaxed_normalize, MatchingPassType.RELAXED),
            (self._numeric_normalize, MatchingPassType.NUMERIC),
        ]

        for normalizer_func, pass_type in normalizers:
            if not unmatched_lines:
                break  # Early termination - all lines matched

            self.logger.debug(
                f"Starting {pass_type} pass with {len(unmatched_lines)} unmatched lines"
            )

            # Build invoice lookup for this normalization strategy
            invoice_lookup = self._build_invoice_lookup(invoices, normalizer_func)

            # Match unmatched lines using current strategy
            matched, still_unmatched = self._match_payments_with_lookup(
                unmatched_lines, invoice_lookup, normalizer_func, pass_type
            )

            all_matched.extend(matched)
            unmatched_lines = still_unmatched

            self.logger.debug(f"{pass_type} pass matched {len(matched)} lines")

        return all_matched, unmatched_lines

    def _build_invoice_lookup(
        self, invoices: List[Dict[str, Any]], normalizer_func
    ) -> Dict[str, Dict[str, Any]]:
        """
        Build O(1) lookup dictionary for invoices using specified normalization.

        Args:
            invoices: List of invoice records
            normalizer_func: Function to normalize invoice numbers

        Returns:
            Dictionary mapping normalized invoice numbers to invoice records
        """
        lookup = {}

        for invoice in invoices:
            invoice_number = invoice.get("invoice_number", "")
            if not invoice_number:
                continue

            normalized = normalizer_func(invoice_number)
            if normalized and normalized not in lookup:
                # First match wins for each normalized form
                lookup[normalized] = invoice

        return lookup

    def _match_payments_with_lookup(
        self,
        payment_lines: List[Dict[str, Any]],
        invoice_lookup: Dict[str, Dict[str, Any]],
        normalizer_func,
        pass_type: MatchingPassType,
    ) -> Tuple[List[InvoiceMatchResult], List[Dict[str, Any]]]:
        """
        Match payment lines against invoice lookup using normalization function.

        Args:
            payment_lines: Payment lines to match
            invoice_lookup: Pre-built invoice lookup dictionary
            normalizer_func: Normalization function to apply
            pass_type: Type of matching pass for statistics

        Returns:
            Tuple of (matched_results, unmatched_lines)
        """
        matched = []
        unmatched = []

        for line in payment_lines:
            line_invoice_number = line.get("invoice_number", "")
            if not line_invoice_number:
                unmatched.append(line)
                continue

            # Normalize payment line invoice number
            normalized_line_number = normalizer_func(line_invoice_number)

            # Look for match in invoice lookup
            if normalized_line_number in invoice_lookup:
                matched_invoice = invoice_lookup[normalized_line_number]

                match_result = InvoiceMatchResult(
                    line_id=UUID(line["id"]),
                    line_invoice_number=line_invoice_number,
                    matched_invoice_id=UUID(matched_invoice["id"]),
                    matched_invoice_number=matched_invoice["invoice_number"],
                    match_type=pass_type,
                    confidence=self._calculate_match_confidence(
                        pass_type,
                        line_invoice_number,
                        matched_invoice["invoice_number"],
                    ),
                )

                matched.append(match_result)
            else:
                unmatched.append(line)

        return matched, unmatched

    # Normalization Functions

    def _exact_normalize(self, invoice_number: str) -> str:
        """
        Exact normalization: case-insensitive with whitespace trimming.

        Example: "  InV-123  " -> "INV-123"
        """
        if not invoice_number:
            return ""
        return invoice_number.strip().upper()

    def _relaxed_normalize(self, invoice_number: str) -> str:
        """
        Relaxed normalization: remove all non-alphanumeric characters.

        Example: "INV-123" -> "INV123", "invoice#456" -> "INVOICE456"
        """
        if not invoice_number:
            return ""
        normalized = self._exact_normalize(invoice_number)
        return "".join(char for char in normalized if char.isalnum())

    def _numeric_normalize(self, invoice_number: str) -> str:
        """
        Numeric normalization: extract digits only.

        Example: "INV-123" -> "123", "BILL/789/v2" -> "789"
        """
        if not invoice_number:
            return ""
        return "".join(char for char in invoice_number if char.isdigit())

    def _calculate_match_confidence(
        self, pass_type: MatchingPassType, original: str, matched: str
    ) -> Decimal:
        """Calculate confidence score based on match type and string similarity"""
        base_confidence = {
            MatchingPassType.EXACT: Decimal("0.95"),
            MatchingPassType.RELAXED: Decimal("0.85"),
            MatchingPassType.NUMERIC: Decimal("0.70"),
        }

        confidence = base_confidence.get(pass_type, Decimal("0.5"))

        # Adjust based on string similarity (simplified)
        if original.upper() == matched.upper():
            confidence = min(confidence + Decimal("0.05"), Decimal("1.0"))

        return confidence

    # Database Operations

    async def _fetch_remittance_lines(
        self, remittance_id: UUID
    ) -> List[Dict[str, Any]]:
        """Fetch payment lines for remittance"""
        try:
            response = (
                self.db.table("remittance_lines")
                .select("id, invoice_number, ai_paid_amount, ai_invoice_id")
                .eq("remittance_id", str(remittance_id))
                .execute()
            )

            return response.data or []

        except Exception as e:
            self.logger.error(f"Failed to fetch remittance lines: {str(e)}")
            raise

    async def _fetch_organization_invoices(
        self, organization_id: UUID
    ) -> List[Dict[str, Any]]:
        """Fetch all invoices for organization (excluding deleted)"""
        try:
            response = (
                self.db.table("invoices")
                .select("id, invoice_number, xero_invoice_id, total, status")
                .eq("organization_id", str(organization_id))
                .neq("status", "DELETED")
                .execute()
            )

            return response.data or []

        except Exception as e:
            self.logger.error(f"Failed to fetch invoices: {str(e)}")
            raise

    async def _update_matched_lines_in_db(
        self, matched_results: List[InvoiceMatchResult], org_context: Dict[str, Any]
    ):
        """Batch update matched lines with invoice IDs"""
        if not matched_results:
            return

        try:
            updates = []
            for match in matched_results:
                updates.append(
                    {
                        "id": str(match.line_id),
                        "ai_invoice_id": str(match.matched_invoice_id),
                    }
                )

            # Batch update in chunks
            for i in range(0, len(updates), self.batch_size):
                batch = updates[i : i + self.batch_size]

                for update in batch:
                    self.db.table("remittance_lines").update(
                        {"ai_invoice_id": update["ai_invoice_id"]}
                    ).eq("id", update["id"]).execute()

            self.logger.info(
                f"Updated {len(matched_results)} matched lines in database"
            )

        except Exception as e:
            self.logger.error(f"Failed to update matched lines: {str(e)}")
            raise

    # Result Compilation

    def _compile_matching_result(
        self,
        all_matched: List[InvoiceMatchResult],
        unmatched_lines: List[Dict[str, Any]],
        original_lines: List[Dict[str, Any]],
        processing_time_ms: int,
    ) -> InvoiceMatchingResult:
        """Compile comprehensive matching result with statistics"""

        total_lines = len(original_lines)
        matched_count = len(all_matched)
        unmatched_count = len(unmatched_lines)

        # Calculate pass-specific statistics
        exact_matches = len(
            [m for m in all_matched if m.match_type == MatchingPassType.EXACT]
        )
        relaxed_matches = len(
            [m for m in all_matched if m.match_type == MatchingPassType.RELAXED]
        )
        numeric_matches = len(
            [m for m in all_matched if m.match_type == MatchingPassType.NUMERIC]
        )

        # Calculate match percentage
        match_percentage = (
            Decimal(matched_count) / Decimal(total_lines) * 100
            if total_lines > 0
            else Decimal("0")
        )

        summary = InvoiceMatchingSummary(
            total_lines=total_lines,
            matched_count=matched_count,
            unmatched_count=unmatched_count,
            match_percentage=match_percentage.quantize(Decimal("0.1")),
            all_matched=unmatched_count == 0,
            exact_matches=exact_matches,
            relaxed_matches=relaxed_matches,
            numeric_matches=numeric_matches,
            processing_time_ms=processing_time_ms,
        )

        return InvoiceMatchingResult(
            summary=summary, matches=all_matched, unmatched_lines=unmatched_lines
        )

    def _create_empty_result(self) -> InvoiceMatchingResult:
        """Create result for empty remittance"""
        summary = InvoiceMatchingSummary(
            total_lines=0,
            matched_count=0,
            unmatched_count=0,
            match_percentage=Decimal("0"),
            all_matched=True,
        )
        return InvoiceMatchingResult(summary=summary, matches=[], unmatched_lines=[])

    def _create_no_invoices_result(
        self, remittance_lines: List[Dict[str, Any]]
    ) -> InvoiceMatchingResult:
        """Create result when no invoices available for matching"""
        summary = InvoiceMatchingSummary(
            total_lines=len(remittance_lines),
            matched_count=0,
            unmatched_count=len(remittance_lines),
            match_percentage=Decimal("0"),
            all_matched=False,
        )
        return InvoiceMatchingResult(
            summary=summary, matches=[], unmatched_lines=remittance_lines
        )


class InvoiceMatchingError(Exception):
    """Exception for invoice matching failures"""

    pass


# Example Usage and Testing
async def example_matching_workflow():
    """Example of complete matching workflow"""

    # Mock database client (replace with actual implementation)
    class MockDatabaseClient:
        def table(self, table_name):
            return self

        def select(self, columns):
            return self

        def eq(self, column, value):
            return self

        def neq(self, column, value):
            return self

        def execute(self):
            # Mock response - replace with real data
            if "remittance_lines" in str(self):
                return type(
                    "Response",
                    (),
                    {
                        "data": [
                            {
                                "id": "1",
                                "invoice_number": "INV-001",
                                "ai_paid_amount": 100.00,
                            },
                            {
                                "id": "2",
                                "invoice_number": "inv 002",
                                "ai_paid_amount": 250.00,
                            },
                            {
                                "id": "3",
                                "invoice_number": "BILL/003",
                                "ai_paid_amount": 150.00,
                            },
                        ]
                    },
                )()
            else:  # invoices
                return type(
                    "Response",
                    (),
                    {
                        "data": [
                            {
                                "id": "101",
                                "invoice_number": "INV-001",
                                "total": 100.00,
                                "status": "AUTHORISED",
                            },
                            {
                                "id": "102",
                                "invoice_number": "INV-002",
                                "total": 250.00,
                                "status": "AUTHORISED",
                            },
                            {
                                "id": "103",
                                "invoice_number": "BILL003",
                                "total": 150.00,
                                "status": "AUTHORISED",
                            },
                        ]
                    },
                )()

        def update(self, data):
            return self

    # Initialize service
    db_client = MockDatabaseClient()
    matching_service = InvoiceMatchingService(db_client)

    # Execute matching
    remittance_id = UUID("12345678-1234-5678-9012-123456789012")
    organization_id = UUID("87654321-4321-8765-2109-876543210987")
    org_context = {"organisation_id": str(organization_id)}

    try:
        result = await matching_service.match_remittance_payments(
            remittance_id, organization_id, org_context
        )

        print(f"Matching Results:")
        print(f"  Total Lines: {result.summary.total_lines}")
        print(f"  Matched: {result.summary.matched_count}")
        print(f"  Unmatched: {result.summary.unmatched_count}")
        print(f"  Match Rate: {result.summary.match_percentage}%")
        print(f"  Processing Time: {result.summary.processing_time_ms}ms")
        print(f"\nPass Breakdown:")
        print(f"  Exact: {result.summary.exact_matches}")
        print(f"  Relaxed: {result.summary.relaxed_matches}")
        print(f"  Numeric: {result.summary.numeric_matches}")

        print(f"\nIndividual Matches:")
        for match in result.matches:
            print(
                f"  {match.line_invoice_number} -> {match.matched_invoice_number} ({match.match_type})"
            )

    except InvoiceMatchingError as e:
        print(f"Matching failed: {e}")


if __name__ == "__main__":
    asyncio.run(example_matching_workflow())
