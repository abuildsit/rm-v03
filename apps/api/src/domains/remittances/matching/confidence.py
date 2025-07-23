"""
Confidence calculation for invoice matching.
"""

from decimal import Decimal
from typing import Optional

from src.domains.remittances.matching.strategies import calculate_similarity_score
from src.domains.remittances.types import MatchingPassType


def calculate_match_confidence(
    match_type: MatchingPassType,
    original_invoice: str,
    matched_invoice: str,
    amount_match: bool = True,
) -> Decimal:
    """
    Calculate confidence score for an invoice match.

    Args:
        match_type: Type of matching algorithm used
        original_invoice: Original invoice number from remittance
        matched_invoice: Matched invoice number from database
        amount_match: Whether amounts match (affects confidence)

    Returns:
        Confidence score between 0.0 and 1.0
    """
    # Base confidence by match type
    base_confidence = {
        MatchingPassType.EXACT: 0.95,
        MatchingPassType.RELAXED: 0.85,
        MatchingPassType.NUMERIC: 0.70,
    }

    confidence = base_confidence.get(match_type, 0.50)

    # Adjust based on string similarity
    similarity = calculate_similarity_score(original_invoice, matched_invoice)

    # Weight the similarity adjustment based on match type
    if match_type == MatchingPassType.EXACT:
        # For exact matches, similarity should be very high
        if similarity < 0.95:
            confidence *= 0.90  # Slight penalty if not perfectly similar
    elif match_type == MatchingPassType.RELAXED:
        # For relaxed matches, use similarity to adjust confidence
        confidence = confidence * (0.7 + 0.3 * similarity)
    elif match_type == MatchingPassType.NUMERIC:
        # For numeric matches, heavily weight similarity
        confidence = confidence * (0.5 + 0.5 * similarity)

    # Penalty for amount mismatch (if we have amount information)
    if not amount_match:
        confidence *= 0.70

    # Ensure confidence stays within bounds
    return Decimal(str(max(0.0, min(1.0, confidence))))


def calculate_overall_confidence(
    line_confidences: list[Optional[Decimal]],
    extraction_confidence: Optional[Decimal] = None,
) -> Decimal:
    """
    Calculate overall confidence for a remittance based on individual line confidences.

    Args:
        line_confidences: List of confidence scores for each line
        extraction_confidence: AI extraction confidence (optional)

    Returns:
        Overall confidence score between 0.0 and 1.0
    """
    # Filter out None values
    valid_confidences = [c for c in line_confidences if c is not None]

    if not valid_confidences:
        # If no matches found, confidence is low
        base_confidence = Decimal("0.20")
    else:
        # Use weighted average of line confidences
        total_lines = len(line_confidences)
        matched_lines = len(valid_confidences)

        # Calculate average confidence of matched lines
        avg_match_confidence = sum(valid_confidences) / Decimal(len(valid_confidences))

        # Apply penalty for unmatched lines
        match_ratio = Decimal(matched_lines) / Decimal(total_lines)
        base_confidence = avg_match_confidence * match_ratio

    # Factor in extraction confidence if available
    if extraction_confidence is not None:
        # Weight both equally
        final_confidence = (
            Decimal(str(base_confidence)) + extraction_confidence
        ) / Decimal("2")
    else:
        final_confidence = Decimal(str(base_confidence))

    return Decimal(str(max(0.0, min(1.0, final_confidence))))


def get_confidence_category(confidence: Decimal) -> str:
    """
    Get human-readable confidence category.

    Args:
        confidence: Confidence score between 0.0 and 1.0

    Returns:
        Confidence category string
    """
    if confidence >= 0.90:
        return "very_high"
    elif confidence >= 0.75:
        return "high"
    elif confidence >= 0.50:
        return "medium"
    elif confidence >= 0.30:
        return "low"
    else:
        return "very_low"


def should_auto_approve(
    confidence: Decimal, threshold: Decimal = Decimal("0.85")
) -> bool:
    """
    Determine if a match should be auto-approved based on confidence.

    Args:
        confidence: Confidence score
        threshold: Minimum confidence for auto-approval

    Returns:
        True if match should be auto-approved
    """
    return confidence >= threshold


def requires_manual_review(
    confidence: Decimal, threshold: Decimal = Decimal("0.50")
) -> bool:
    """
    Determine if a match requires manual review based on confidence.

    Args:
        confidence: Confidence score
        threshold: Maximum confidence for automatic processing

    Returns:
        True if match requires manual review
    """
    return confidence < threshold
