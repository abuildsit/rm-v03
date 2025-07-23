"""
Types and enums for remittances domain.
"""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import List, Optional
from uuid import UUID

from prisma.enums import RemittanceStatus
from pydantic import BaseModel, Field


class MatchingPassType(str, Enum):
    """Types of matching algorithms."""

    EXACT = "exact"
    RELAXED = "relaxed"
    NUMERIC = "numeric"


class RemittanceCreateRequest(BaseModel):
    """Request model for creating a new remittance."""

    filename: str
    file_size: int
    description: Optional[str] = None


class ExtractedPayment(BaseModel):
    """Individual payment extracted from remittance."""

    invoice_number: str
    paid_amount: Decimal


class ExtractedRemittanceData(BaseModel):
    """Structured data extracted from remittance PDF."""

    payment_date: date
    total_amount: Decimal
    payment_reference: Optional[str] = None
    payments: List[ExtractedPayment]
    confidence: Decimal = Field(ge=0, le=1)
    thread_id: Optional[str] = None


class MatchResult(BaseModel):
    """Result of invoice matching for a single line."""

    line_id: UUID
    invoice_number: str
    matched_invoice_id: Optional[UUID] = None
    match_confidence: Optional[Decimal] = Field(None, ge=0, le=1)
    match_type: Optional[MatchingPassType] = None


class RemittanceLineDetail(BaseModel):
    """Detailed remittance line information."""

    id: UUID
    line_number: int
    invoice_number: str
    ai_paid_amount: Optional[Decimal] = None
    manual_paid_amount: Optional[Decimal] = None
    matched_invoice: Optional[dict] = None  # Will contain invoice details
    match_confidence: Optional[Decimal] = Field(None, ge=0, le=1)
    match_type: Optional[MatchingPassType] = None
    notes: Optional[str] = None


class RemittanceSummary(BaseModel):
    """Summary statistics for remittance matching."""

    total_lines: int
    matched_count: int
    unmatched_count: int
    match_percentage: Decimal
    exact_matches: int = 0
    relaxed_matches: int = 0
    numeric_matches: int = 0
    processing_time_ms: int = 0


class RemittanceDetail(BaseModel):
    """Complete remittance details."""

    id: UUID
    filename: str
    upload_date: datetime
    status: RemittanceStatus
    total_amount: Optional[Decimal] = None
    payment_date: Optional[date] = None
    payment_reference: Optional[str] = None
    confidence_score: Optional[Decimal] = Field(None, ge=0, le=1)
    lines: List[RemittanceLineDetail]
    summary: RemittanceSummary


class RemittanceListItem(BaseModel):
    """Remittance list item for overview display."""

    id: UUID
    filename: str
    upload_date: datetime
    status: RemittanceStatus
    total_amount: Optional[Decimal] = None
    lines_count: int
    matched_count: int
    match_percentage: Decimal


class RemittanceOverrideRequest(BaseModel):
    """Request to override a line's invoice match."""

    override_invoice_id: UUID
    notes: Optional[str] = None
