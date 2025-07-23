"""
Normalization strategies for invoice matching.
"""

import re


def exact_normalize(invoice_number: str) -> str:
    """
    Normalize invoice number for exact matching.
    - Trim whitespace
    - Convert to uppercase

    Args:
        invoice_number: Raw invoice number

    Returns:
        Normalized invoice number for exact matching
    """
    return invoice_number.strip().upper()


def relaxed_normalize(invoice_number: str) -> str:
    """
    Normalize invoice number for relaxed matching.
    - Remove all non-alphanumeric characters
    - Convert to uppercase

    Args:
        invoice_number: Raw invoice number

    Returns:
        Normalized invoice number for relaxed matching
    """
    # Remove all non-alphanumeric characters
    cleaned = re.sub(r"[^a-zA-Z0-9]", "", invoice_number)
    return cleaned.upper()


def numeric_normalize(invoice_number: str) -> str:
    """
    Normalize invoice number for numeric matching.
    - Extract only numeric characters
    - Join them together

    Args:
        invoice_number: Raw invoice number

    Returns:
        Normalized invoice number for numeric matching (digits only)
    """
    # Extract all digits
    digits = re.findall(r"\d", invoice_number)
    return "".join(digits)


def generate_variations(invoice_number: str) -> list[str]:
    """
    Generate all normalization variations for an invoice number.

    Args:
        invoice_number: Raw invoice number

    Returns:
        List of normalized variations [exact, relaxed, numeric]
    """
    variations = []

    # Exact normalization
    exact = exact_normalize(invoice_number)
    if exact:
        variations.append(exact)

    # Relaxed normalization
    relaxed = relaxed_normalize(invoice_number)
    if relaxed and relaxed not in variations:
        variations.append(relaxed)

    # Numeric normalization
    numeric = numeric_normalize(invoice_number)
    if numeric and len(numeric) >= 3 and numeric not in variations:  # At least 3 digits
        variations.append(numeric)

    return variations


def build_lookup_table(invoice_numbers: list[str]) -> dict[str, list[str]]:
    """
    Build lookup table for O(1) invoice matching.
    Maps normalized values back to original invoice numbers.

    Args:
        invoice_numbers: List of original invoice numbers

    Returns:
        Dictionary mapping normalized values to original invoice numbers
    """
    lookup: dict[str, list[str]] = {}

    for original in invoice_numbers:
        variations = generate_variations(original)

        for variation in variations:
            if variation not in lookup:
                lookup[variation] = []
            lookup[variation].append(original)

    return lookup


def find_potential_matches(
    target_number: str, lookup_table: dict[str, list[str]]
) -> list[tuple[str, str]]:
    """
    Find potential matches for a target invoice number.

    Args:
        target_number: Invoice number to match
        lookup_table: Pre-built lookup table

    Returns:
        List of (match_type, matched_invoice) tuples
    """
    import sys

    matches = []

    print(
        f"🔍 MATCHING DEBUG: Searching for '{target_number}'",
        file=sys.stderr,
        flush=True,
    )

    # Get all possible normalizations
    exact = exact_normalize(target_number)
    relaxed = relaxed_normalize(target_number)
    numeric = numeric_normalize(target_number)

    print(
        f"  📝 Normalizations: exact='{exact}', relaxed='{relaxed}', numeric='{numeric}'",
        file=sys.stderr,
        flush=True,
    )

    # Collect all potential matches first
    potential_matches = []
    
    # Check exact matches
    if exact in lookup_table:
        for match in lookup_table[exact]:
            potential_matches.append((match, "exact_lookup"))

    # Check relaxed matches  
    if relaxed in lookup_table and relaxed != exact:
        for match in lookup_table[relaxed]:
            potential_matches.append((match, "relaxed_lookup"))

    # Check numeric matches
    if numeric in lookup_table and numeric != relaxed and numeric != exact and len(numeric) >= 3:
        for match in lookup_table[numeric]:
            potential_matches.append((match, "numeric_lookup"))

    # Now determine the correct match type based on actual similarity
    for match, lookup_type in potential_matches:
        match_type = determine_match_type(target_number, match)
        matches.append((match_type, match))
        print(
            f"  ✅ {match_type.upper()} match found: '{target_number}' → '{match}' (via {lookup_type})",
            file=sys.stderr,
            flush=True,
        )

    print(f"  📊 Total matches found: {len(matches)}", file=sys.stderr, flush=True)
    return matches


def determine_match_type(target: str, matched_invoice: str) -> str:
    """
    Determine the actual match type between target and matched invoice.
    
    Args:
        target: The search term from remittance
        matched_invoice: The matched invoice number from database
    
    Returns:
        Match type: "exact", "relaxed", or "numeric"
    """
    # Normalize both for comparison
    target_exact = exact_normalize(target)
    match_exact = exact_normalize(matched_invoice)
    
    # True exact match: both exact normalizations are identical
    if target_exact == match_exact:
        return "exact"
    
    target_relaxed = relaxed_normalize(target)
    match_relaxed = relaxed_normalize(matched_invoice)
    
    # Relaxed match: relaxed normalizations match but exact don't
    if target_relaxed == match_relaxed:
        return "relaxed"
    
    target_numeric = numeric_normalize(target)
    match_numeric = numeric_normalize(matched_invoice)
    
    # Numeric match: only numeric parts match
    if target_numeric == match_numeric and len(target_numeric) >= 3:
        return "numeric"
    
    # Fallback (shouldn't happen with correct lookup table)
    return "relaxed"


def calculate_similarity_score(original: str, target: str) -> float:
    """
    Calculate similarity score between two invoice numbers.
    Used for confidence calculation.

    Args:
        original: Original invoice number
        target: Target invoice number to compare

    Returns:
        Similarity score between 0.0 and 1.0
    """
    if not original or not target:
        return 0.0

    # Normalize both for comparison
    orig_norm = exact_normalize(original)
    target_norm = exact_normalize(target)

    if orig_norm == target_norm:
        return 1.0

    # Check relaxed match
    orig_relaxed = relaxed_normalize(original)
    target_relaxed = relaxed_normalize(target)

    if orig_relaxed == target_relaxed:
        return 0.85

    # Check numeric match
    orig_numeric = numeric_normalize(original)
    target_numeric = numeric_normalize(target)

    if orig_numeric == target_numeric and len(orig_numeric) >= 3:
        return 0.70

    # Calculate character-level similarity as fallback
    return _calculate_char_similarity(orig_norm, target_norm)


def _calculate_char_similarity(str1: str, str2: str) -> float:
    """
    Calculate character-level similarity between two strings.

    Args:
        str1: First string
        str2: Second string

    Returns:
        Similarity score between 0.0 and 1.0
    """
    if not str1 or not str2:
        return 0.0

    # Simple Jaccard similarity on character level
    set1 = set(str1.lower())
    set2 = set(str2.lower())

    intersection = len(set1 & set2)
    union = len(set1 | set2)

    if union == 0:
        return 0.0

    return intersection / union
