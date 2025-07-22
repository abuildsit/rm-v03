"""
RemitMatch Invoice Normalization Functions - Implementation Examples
===================================================================

This file demonstrates the normalization strategies used in RemitMatch's
invoice matching system for handling various invoice number formats.
"""

import re
import string
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Set, Tuple


class NormalizationType(str, Enum):
    """Types of normalization strategies"""

    EXACT = "exact"
    RELAXED = "relaxed"
    NUMERIC = "numeric"
    PHONETIC = "phonetic"  # Advanced option
    FUZZY = "fuzzy"  # Advanced option


@dataclass
class NormalizationResult:
    """Result of normalization operation"""

    original: str
    normalized: str
    normalization_type: NormalizationType
    confidence: float
    transformations_applied: List[str]


class InvoiceNormalizer:
    """
    Comprehensive invoice number normalization service.

    This class provides multiple normalization strategies for handling
    various invoice number formats and improving matching accuracy.
    """

    def __init__(self):
        self.transformation_log = []

        # Common invoice prefixes and patterns
        self.common_prefixes = {
            "INVOICE",
            "INV",
            "BILL",
            "RECEIPT",
            "RCP",
            "TXN",
            "TRANSACTION",
            "ORDER",
            "ORD",
            "REF",
            "REFERENCE",
        }

        # Common separators
        self.separators = {"-", "_", "/", "\\", ".", ":", ";", "|", "#", " "}

        # Regex patterns for common invoice formats
        self.invoice_patterns = [
            r"^[A-Za-z]+-\d+$",  # INV-123
            r"^[A-Za-z]+\d+$",  # INV123
            r"^[A-Za-z]+/\d+$",  # BILL/456
            r"^\d+$",  # 789
            r"^[A-Za-z]+\s+\d+$",  # INVOICE 123
            r"^[A-Za-z]+-[A-Za-z]+-\d+$",  # INV-ABC-123
        ]

    def exact_normalize(self, invoice_number: str) -> NormalizationResult:
        """
        Exact normalization: case-insensitive with whitespace trimming.

        This is the most conservative normalization, handling only:
        - Leading/trailing whitespace
        - Case differences

        Examples:
        - "  InV-123  " -> "INV-123"
        - "bill-456" -> "BILL-456"
        - "Invoice/789 " -> "INVOICE/789"
        """
        if not invoice_number:
            return NormalizationResult(
                original="",
                normalized="",
                normalization_type=NormalizationType.EXACT,
                confidence=1.0,
                transformations_applied=[],
            )

        transformations = []
        normalized = invoice_number

        # Remove leading/trailing whitespace
        if normalized != normalized.strip():
            transformations.append("trim_whitespace")
            normalized = normalized.strip()

        # Convert to uppercase
        if normalized != normalized.upper():
            transformations.append("uppercase")
            normalized = normalized.upper()

        return NormalizationResult(
            original=invoice_number,
            normalized=normalized,
            normalization_type=NormalizationType.EXACT,
            confidence=1.0 if normalized == invoice_number.strip().upper() else 0.95,
            transformations_applied=transformations,
        )

    def relaxed_normalize(self, invoice_number: str) -> NormalizationResult:
        """
        Relaxed normalization: remove all non-alphanumeric characters.

        This handles punctuation and separator differences:
        - Remove all special characters and spaces
        - Keep only letters and numbers
        - Convert to uppercase

        Examples:
        - "INV-123" -> "INV123"
        - "BILL/456" -> "BILL456"
        - "invoice #789" -> "INVOICE789"
        - "REF: ABC-123" -> "REFABC123"
        """
        if not invoice_number:
            return NormalizationResult(
                original="",
                normalized="",
                normalization_type=NormalizationType.RELAXED,
                confidence=1.0,
                transformations_applied=[],
            )

        transformations = []

        # Start with exact normalization
        exact_result = self.exact_normalize(invoice_number)
        normalized = exact_result.normalized
        transformations.extend(exact_result.transformations_applied)

        # Remove all non-alphanumeric characters
        original_normalized = normalized
        normalized = "".join(char for char in normalized if char.isalnum())

        if normalized != original_normalized:
            transformations.append("remove_special_chars")

        # Calculate confidence based on how much was changed
        char_retention_ratio = (
            len(normalized) / len(original_normalized) if original_normalized else 1.0
        )
        confidence = 0.85 * char_retention_ratio

        return NormalizationResult(
            original=invoice_number,
            normalized=normalized,
            normalization_type=NormalizationType.RELAXED,
            confidence=confidence,
            transformations_applied=transformations,
        )

    def numeric_normalize(self, invoice_number: str) -> NormalizationResult:
        """
        Numeric normalization: extract digits only.

        This is the most aggressive normalization, extracting only numeric content:
        - Remove all non-digit characters
        - Preserve digit sequence

        Examples:
        - "INV-123" -> "123"
        - "BILL/789/v2" -> "789"
        - "ORDER#456-ABC" -> "456"
        - "REF:2024-001" -> "2024001"
        """
        if not invoice_number:
            return NormalizationResult(
                original="",
                normalized="",
                normalization_type=NormalizationType.NUMERIC,
                confidence=1.0,
                transformations_applied=[],
            )

        transformations = ["extract_digits_only"]

        # Extract all digits
        normalized = "".join(char for char in invoice_number if char.isdigit())

        # Calculate confidence based on digit retention
        original_digit_count = sum(1 for char in invoice_number if char.isdigit())
        confidence = 0.7 if normalized else 0.0

        # Adjust confidence based on digit retention ratio
        if original_digit_count > 0:
            digit_retention = len(normalized) / original_digit_count
            confidence *= digit_retention

        return NormalizationResult(
            original=invoice_number,
            normalized=normalized,
            normalization_type=NormalizationType.NUMERIC,
            confidence=confidence,
            transformations_applied=transformations,
        )

    def advanced_normalize(
        self, invoice_number: str, strategy: str = "smart"
    ) -> NormalizationResult:
        """
        Advanced normalization with pattern recognition.

        This method analyzes the invoice format and applies appropriate normalization:
        - Pattern recognition for common formats
        - Intelligent prefix/suffix handling
        - Context-aware transformations

        Args:
            invoice_number: Original invoice number
            strategy: "smart", "aggressive", or "conservative"
        """
        if not invoice_number:
            return self.numeric_normalize(invoice_number)

        transformations = []
        normalized = invoice_number.strip().upper()

        # Detect format pattern
        pattern_type = self._detect_pattern(normalized)
        transformations.append(f"detected_pattern_{pattern_type}")

        if strategy == "smart":
            # Apply format-specific normalization
            if pattern_type == "prefixed_numeric":
                # INV-123 -> keep structure but normalize separators
                normalized = self._normalize_prefixed_format(normalized)
                transformations.append("normalize_prefixed")
            elif pattern_type == "pure_numeric":
                # Already optimal for matching
                pass
            elif pattern_type == "complex":
                # Apply relaxed normalization for complex formats
                return self.relaxed_normalize(invoice_number)

        elif strategy == "aggressive":
            # Always use numeric extraction
            return self.numeric_normalize(invoice_number)

        elif strategy == "conservative":
            # Use exact normalization only
            return self.exact_normalize(invoice_number)

        return NormalizationResult(
            original=invoice_number,
            normalized=normalized,
            normalization_type=NormalizationType.RELAXED,
            confidence=0.9,
            transformations_applied=transformations,
        )

    def batch_normalize(
        self,
        invoice_numbers: List[str],
        strategy: NormalizationType = NormalizationType.RELAXED,
    ) -> List[NormalizationResult]:
        """
        Batch normalization for efficient processing.

        Args:
            invoice_numbers: List of invoice numbers to normalize
            strategy: Normalization strategy to apply

        Returns:
            List of normalization results
        """
        results = []

        for invoice_number in invoice_numbers:
            if strategy == NormalizationType.EXACT:
                result = self.exact_normalize(invoice_number)
            elif strategy == NormalizationType.RELAXED:
                result = self.relaxed_normalize(invoice_number)
            elif strategy == NormalizationType.NUMERIC:
                result = self.numeric_normalize(invoice_number)
            else:
                result = self.advanced_normalize(invoice_number)

            results.append(result)

        return results

    def create_normalization_lookup(
        self,
        invoice_numbers: List[str],
        strategy: NormalizationType = NormalizationType.RELAXED,
    ) -> Dict[str, str]:
        """
        Create lookup dictionary for efficient matching.

        Args:
            invoice_numbers: List of invoice numbers
            strategy: Normalization strategy

        Returns:
            Dictionary mapping normalized forms to original invoice numbers
        """
        lookup = {}

        results = self.batch_normalize(invoice_numbers, strategy)

        for result in results:
            if result.normalized and result.normalized not in lookup:
                # First occurrence wins for duplicate normalized forms
                lookup[result.normalized] = result.original

        return lookup

    def _detect_pattern(self, invoice_number: str) -> str:
        """Detect common invoice number patterns"""
        for i, pattern in enumerate(self.invoice_patterns):
            if re.match(pattern, invoice_number):
                return f"pattern_{i}"
        return "unknown"

    def _normalize_prefixed_format(self, invoice_number: str) -> str:
        """Normalize prefixed invoice formats (INV-123, BILL/456)"""
        # Replace various separators with standard dash
        for separator in self.separators:
            if separator in invoice_number:
                parts = invoice_number.split(separator, 1)
                if len(parts) == 2 and parts[0].isalpha() and parts[1].isdigit():
                    return f"{parts[0]}-{parts[1]}"

        return invoice_number

    def analyze_normalization_effectiveness(
        self, invoice_pairs: List[Tuple[str, str]]
    ) -> Dict[str, float]:
        """
        Analyze how well different normalization strategies work for given data.

        Args:
            invoice_pairs: List of (invoice1, invoice2) that should match

        Returns:
            Dictionary with effectiveness scores for each strategy
        """
        strategies = [
            NormalizationType.EXACT,
            NormalizationType.RELAXED,
            NormalizationType.NUMERIC,
        ]

        effectiveness = {}

        for strategy in strategies:
            matches = 0
            total = len(invoice_pairs)

            for inv1, inv2 in invoice_pairs:
                result1 = self.batch_normalize([inv1], strategy)[0]
                result2 = self.batch_normalize([inv2], strategy)[0]

                if result1.normalized == result2.normalized:
                    matches += 1

            effectiveness[strategy.value] = matches / total if total > 0 else 0.0

        return effectiveness


# Utility functions for common use cases


def normalize_for_matching(invoice_number: str, pass_type: str = "relaxed") -> str:
    """
    Quick normalization function for matching operations.

    Args:
        invoice_number: Invoice number to normalize
        pass_type: "exact", "relaxed", or "numeric"

    Returns:
        Normalized invoice number string
    """
    normalizer = InvoiceNormalizer()

    if pass_type == "exact":
        result = normalizer.exact_normalize(invoice_number)
    elif pass_type == "relaxed":
        result = normalizer.relaxed_normalize(invoice_number)
    elif pass_type == "numeric":
        result = normalizer.numeric_normalize(invoice_number)
    else:
        raise ValueError(f"Invalid pass_type: {pass_type}")

    return result.normalized


def build_matching_lookup(
    invoice_data: List[Dict[str, str]], pass_type: str = "relaxed"
) -> Dict[str, Dict[str, str]]:
    """
    Build lookup dictionary for invoice matching.

    Args:
        invoice_data: List of invoice dictionaries with 'invoice_number' key
        pass_type: Normalization strategy to use

    Returns:
        Dictionary mapping normalized numbers to invoice data
    """
    normalizer = InvoiceNormalizer()
    lookup = {}

    for invoice in invoice_data:
        invoice_number = invoice.get("invoice_number", "")
        if not invoice_number:
            continue

        normalized = normalize_for_matching(invoice_number, pass_type)
        if normalized and normalized not in lookup:
            lookup[normalized] = invoice

    return lookup


# Example usage and testing
def demonstrate_normalization():
    """Demonstrate various normalization strategies"""

    # Sample invoice numbers with various formats
    sample_invoices = [
        "  INV-123  ",  # Whitespace and case
        "inv-123",  # Case difference
        "INV/123",  # Different separator
        "INVOICE#123",  # Different separator
        "BILL 123",  # Space separator
        "ORDER-ABC-123",  # Complex format
        "123",  # Pure numeric
        "REF:2024-001",  # Complex with year
        "TXN_456_v2",  # Multiple separators
    ]

    normalizer = InvoiceNormalizer()

    print("Normalization Demonstration")
    print("=" * 50)

    for invoice in sample_invoices:
        print(f"\nOriginal: '{invoice}'")

        # Test all normalization strategies
        exact = normalizer.exact_normalize(invoice)
        relaxed = normalizer.relaxed_normalize(invoice)
        numeric = normalizer.numeric_normalize(invoice)

        print(f"  Exact:   '{exact.normalized}' (confidence: {exact.confidence:.2f})")
        print(
            f"  Relaxed: '{relaxed.normalized}' (confidence: {relaxed.confidence:.2f})"
        )
        print(
            f"  Numeric: '{numeric.normalized}' (confidence: {numeric.confidence:.2f})"
        )


def test_matching_scenarios():
    """Test normalization effectiveness for common matching scenarios"""

    # Test cases: pairs that should match after normalization
    test_pairs = [
        ("INV-123", "inv 123"),  # Case and separator difference
        ("BILL/456", "BILL-456"),  # Separator difference
        ("ORDER 789", "ORDER789"),  # Space removal
        ("REF:001", "REF-001"),  # Punctuation difference
        ("TXN_123_v2", "TXN123"),  # Complex to simple
    ]

    normalizer = InvoiceNormalizer()
    effectiveness = normalizer.analyze_normalization_effectiveness(test_pairs)

    print("\nNormalization Effectiveness Analysis")
    print("=" * 40)
    for strategy, score in effectiveness.items():
        print(f"{strategy.capitalize()}: {score:.1%} matching rate")


if __name__ == "__main__":
    demonstrate_normalization()
    test_matching_scenarios()
