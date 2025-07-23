"""
Type definitions for AI services.
"""

from typing import NamedTuple, TypedDict


class AIPaymentDict(TypedDict):
    """Typed dict for AI extracted payment data."""

    invoice_number: str
    paid_amount: float


class AIExtractionDict(TypedDict):
    """Typed dict for AI extraction response."""

    payment_date: str
    total_amount: float
    payment_reference: str
    payments: list[AIPaymentDict]
    confidence: float


class AIExtractionResult(NamedTuple):
    """Result containing both extracted data and OpenAI thread ID."""

    data: AIExtractionDict
    thread_id: str
