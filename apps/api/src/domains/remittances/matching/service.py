"""
Matching service for intelligent invoice matching using three-pass algorithm.
"""

import logging
import time
from decimal import Decimal

# No typing imports needed - using Python 3.12+ type hints
from uuid import UUID

from prisma.enums import InvoiceStatus
from prisma.models import Invoice

from prisma import Prisma
from src.domains.remittances.exceptions import MatchingFailedError
from src.domains.remittances.matching.confidence import calculate_match_confidence
from src.domains.remittances.matching.strategies import (
    build_lookup_table,
    find_potential_matches,
)
from src.domains.remittances.types import (
    ExtractedPayment,
    MatchingPassType,
    MatchResult,
    RemittanceSummary,
)

logger = logging.getLogger(__name__)


class MatchingService:
    """Service for matching extracted remittance data against invoices."""

    def __init__(self, db: Prisma) -> None:
        self.db = db

    async def match_payments_to_invoices(
        self,
        payments: list[ExtractedPayment],
        organization_id: UUID,
        remittance_id: UUID,
    ) -> tuple[list[MatchResult], RemittanceSummary]:
        """
        Match extracted payments against organization invoices using
        three-pass algorithm.

        Args:
            payments: List of extracted payments
            organization_id: Organization ID for invoice lookup
            remittance_id: Remittance ID for result tracking

        Returns:
            Tuple of (match results, matching summary)

        Raises:
            MatchingFailedError: If matching process fails
        """
        start_time = time.time()

        try:
            # Get organization invoices for matching
            invoices = await self._get_organization_invoices(organization_id)

            if not invoices:
                logger.warning(f"No invoices found for organization {organization_id}")
                return self._create_empty_results(payments, remittance_id)

            # Build lookup table for O(1) matching
            invoice_map = {
                inv.invoiceNumber: inv for inv in invoices if inv.invoiceNumber
            }
            lookup_table = build_lookup_table(list(invoice_map.keys()))

            logger.info(
                f"Built lookup table with {len(lookup_table)} variations "
                f"from {len(invoice_map)} invoices"
            )

            # Debug: Show what invoices we're working with
            import sys

            print(
                f"🗂️ INVOICE DEBUG: {len(invoice_map)} invoices available:",
                file=sys.stderr,
                flush=True,
            )
            for inv_num in sorted(invoice_map.keys())[:10]:  # Show first 10
                print(f"  - '{inv_num}'", file=sys.stderr, flush=True)
            if len(invoice_map) > 10:
                print(
                    f"  ... and {len(invoice_map) - 10} more",
                    file=sys.stderr,
                    flush=True,
                )

            # Debug: Show some lookup table entries
            print(
                f"🔍 LOOKUP TABLE DEBUG: {len(lookup_table)} normalized variations:",
                file=sys.stderr,
                flush=True,
            )
            for norm_key, orig_invoices in sorted(
                list(lookup_table.items())[:15]
            ):  # Show first 15
                print(f"  '{norm_key}' → {orig_invoices}", file=sys.stderr, flush=True)
            if len(lookup_table) > 15:
                print(
                    f"  ... and {len(lookup_table) - 15} more variations",
                    file=sys.stderr,
                    flush=True,
                )

            # Process each payment
            results = []
            match_stats = {"exact": 0, "relaxed": 0, "numeric": 0, "unmatched": 0}

            for i, payment in enumerate(payments):
                match_result = await self._match_single_payment(
                    payment=payment,
                    remittance_id=remittance_id,
                    line_number=i + 1,
                    lookup_table=lookup_table,
                    invoice_map=invoice_map,
                )

                results.append(match_result)

                # Update statistics
                if match_result.match_type:
                    match_stats[match_result.match_type.value] += 1
                else:
                    match_stats["unmatched"] += 1

            # Calculate processing time
            processing_time_ms = int((time.time() - start_time) * 1000)

            # Create summary
            summary = RemittanceSummary(
                total_lines=len(payments),
                matched_count=len([r for r in results if r.matched_invoice_id]),
                unmatched_count=len([r for r in results if not r.matched_invoice_id]),
                match_percentage=Decimal(
                    str(
                        len([r for r in results if r.matched_invoice_id])
                        / len(payments)
                        * 100
                    )
                    if payments
                    else "0"
                ),
                exact_matches=match_stats["exact"],
                relaxed_matches=match_stats["relaxed"],
                numeric_matches=match_stats["numeric"],
                processing_time_ms=processing_time_ms,
            )

            logger.info(
                f"Matching completed: {summary.matched_count}/"
                f"{summary.total_lines} matched in {processing_time_ms}ms"
            )

            return results, summary

        except Exception as e:
            logger.error(f"Matching failed: {e}")
            raise MatchingFailedError(f"Failed to match payments: {str(e)}")

    async def _match_single_payment(
        self,
        payment: ExtractedPayment,
        remittance_id: UUID,
        line_number: int,
        lookup_table: dict[str, list[str]],
        invoice_map: dict[str, Invoice],
    ) -> MatchResult:
        """
        Match a single payment against invoices using three-pass strategy.

        Args:
            payment: Payment to match
            remittance_id: Remittance ID
            line_number: Line number for tracking
            lookup_table: Pre-built lookup table
            invoice_map: Map of invoice numbers to invoice objects

        Returns:
            Match result for the payment
        """
        # Find potential matches using three-pass strategy
        potential_matches = find_potential_matches(payment.invoice_number, lookup_table)

        if not potential_matches:
            # No matches found
            return MatchResult(
                line_id=UUID(int=line_number),  # Temporary ID
                invoice_number=payment.invoice_number,
                matched_invoice_id=None,
                match_confidence=None,
                match_type=None,
            )

        # Select the best match based on match type priority (exact > relaxed > numeric)
        match_type_str, matched_invoice_number = self._select_best_match(potential_matches)
        match_type = MatchingPassType(match_type_str)

        # Get the matched invoice
        matched_invoice = invoice_map[matched_invoice_number]

        # Calculate confidence
        amount_match = self._check_amount_match(payment.paid_amount, matched_invoice)
        confidence = calculate_match_confidence(
            match_type=match_type,
            original_invoice=payment.invoice_number,
            matched_invoice=matched_invoice_number,
            amount_match=amount_match,
        )

        logger.debug(
            f"Matched '{payment.invoice_number}' to '{matched_invoice_number}' "
            f"via {match_type.value} with confidence {confidence}"
        )

        return MatchResult(
            line_id=UUID(int=line_number),  # Temporary ID
            invoice_number=payment.invoice_number,
            matched_invoice_id=UUID(matched_invoice.id),
            match_confidence=confidence,
            match_type=match_type,
        )

    def _check_amount_match(
        self,
        payment_amount: Decimal,
        invoice: Invoice,
        tolerance: Decimal = Decimal("0.01"),
    ) -> bool:
        """
        Check if payment amount matches invoice amount within tolerance.

        Args:
            payment_amount: Amount from remittance
            invoice: Matched invoice
            tolerance: Acceptable difference

        Returns:
            True if amounts match within tolerance
        """
        if not invoice.total:
            return False

        difference = abs(payment_amount - invoice.total)
        return difference <= tolerance

    def _select_best_match(self, potential_matches: list[tuple[str, str]]) -> tuple[str, str]:
        """
        Select the best match from potential matches based on match type priority.
        
        Priority order: exact > relaxed > numeric
        
        Args:
            potential_matches: List of (match_type, matched_invoice) tuples
            
        Returns:
            The best match tuple (match_type, matched_invoice)
        """
        # Define priority order (lower number = higher priority)
        match_priority = {
            "exact": 1,
            "relaxed": 2, 
            "numeric": 3
        }
        
        # Sort matches by priority (exact matches first)
        sorted_matches = sorted(
            potential_matches, 
            key=lambda x: match_priority.get(x[0], 999)
        )
        
        return sorted_matches[0]

    async def _get_organization_invoices(self, organization_id: UUID) -> list[Invoice]:
        """
        Get all active invoices for an organization.

        Args:
            organization_id: Organization ID

        Returns:
            List of organization invoices
        """
        try:
            invoices = await self.db.invoice.find_many(
                where={
                    "organizationId": str(organization_id),
                    "invoiceNumber": {"not": ""},  # Only invoices with numbers
                    "status": InvoiceStatus.AUTHORISED,  # Focus on authorized invoices
                }
            )

            return invoices

        except Exception as e:
            logger.error(f"Failed to fetch invoices: {e}")
            raise MatchingFailedError(f"Failed to fetch invoices: {str(e)}")

    def _create_empty_results(
        self, payments: list[ExtractedPayment], remittance_id: UUID
    ) -> tuple[list[MatchResult], RemittanceSummary]:
        """
        Create empty match results when no invoices are available.

        Args:
            payments: List of payments
            remittance_id: Remittance ID

        Returns:
            Empty match results and summary
        """
        results = [
            MatchResult(
                line_id=UUID(int=i + 1),  # Temporary ID
                invoice_number=payment.invoice_number,
                matched_invoice_id=None,
                match_confidence=None,
                match_type=None,
            )
            for i, payment in enumerate(payments)
        ]

        summary = RemittanceSummary(
            total_lines=len(payments),
            matched_count=0,
            unmatched_count=len(payments),
            match_percentage=Decimal("0"),
            exact_matches=0,
            relaxed_matches=0,
            numeric_matches=0,
            processing_time_ms=0,
        )

        return results, summary
