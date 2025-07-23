import asyncio
import re
import sys
from typing import Dict, List, Optional, Tuple


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


async def build_exact_lookup(invoice_numbers: List[str]) -> Dict[str, List[str]]:
    """Build lookup table for exact matching."""
    lookup: Dict[str, List[str]] = {}

    for original in invoice_numbers:
        exact = exact_normalize(original)
        if exact:
            if exact not in lookup:
                lookup[exact] = []
            lookup[exact].append(original)

    return lookup


async def build_relaxed_lookup(invoice_numbers: List[str]) -> Dict[str, List[str]]:
    """Build lookup table for relaxed matching."""
    lookup: Dict[str, List[str]] = {}

    for original in invoice_numbers:
        relaxed = relaxed_normalize(original)
        if relaxed:
            if relaxed not in lookup:
                lookup[relaxed] = []
            lookup[relaxed].append(original)

    return lookup


async def build_numeric_lookup(invoice_numbers: List[str]) -> Dict[str, List[str]]:
    """Build lookup table for numeric matching."""
    lookup: Dict[str, List[str]] = {}

    for original in invoice_numbers:
        numeric = numeric_normalize(original)
        if numeric and len(numeric) >= 3:  # At least 3 digits
            if numeric not in lookup:
                lookup[numeric] = []
            lookup[numeric].append(original)

    return lookup


async def try_exact_match(
    target: str, lookup_table: Dict[str, List[str]]
) -> Optional[str]:
    """Try to find exact match for target."""
    normalized = exact_normalize(target)
    matches = lookup_table.get(normalized, [])
    return matches[0] if matches else None


async def try_relaxed_match(
    target: str, lookup_table: Dict[str, List[str]]
) -> Optional[str]:
    """Try to find relaxed match for target."""
    normalized = relaxed_normalize(target)
    matches = lookup_table.get(normalized, [])
    return matches[0] if matches else None


async def try_numeric_match(
    target: str, lookup_table: Dict[str, List[str]]
) -> Optional[str]:
    """Try to find numeric match for target."""
    normalized = numeric_normalize(target)
    if len(normalized) >= 3:
        matches = lookup_table.get(normalized, [])
        return matches[0] if matches else None
    return None


async def find_best_match_concurrent(
    target_number: str,
    exact_lookup: Dict[str, List[str]],
    relaxed_lookup: Dict[str, List[str]],
    numeric_lookup: Dict[str, List[str]],
) -> Optional[Tuple[str, str]]:
    """
    Find the best match using concurrent async matching with priority.

    Args:
        target_number: Invoice number to match
        exact_lookup: Lookup table for exact matches
        relaxed_lookup: Lookup table for relaxed matches
        numeric_lookup: Lookup table for numeric matches

    Returns:
        Tuple of (match_type, matched_invoice) or None if no match
    """
    print(
        f"🔍 ASYNC MATCHING DEBUG: Searching for '{target_number}'",
        file=sys.stderr,
        flush=True,
    )

    # Start all three match types concurrently
    exact_task = asyncio.create_task(try_exact_match(target_number, exact_lookup))
    relaxed_task = asyncio.create_task(try_relaxed_match(target_number, relaxed_lookup))
    numeric_task = asyncio.create_task(try_numeric_match(target_number, numeric_lookup))

    # Wait for all to complete
    exact_result, relaxed_result, numeric_result = await asyncio.gather(
        exact_task, relaxed_task, numeric_task
    )

    # Return first successful match in priority order (exact > relaxed > numeric)
    if exact_result:
        print(
            f"  ✅ EXACT match found: '{target_number}' → '{exact_result}'",
            file=sys.stderr,
            flush=True,
        )
        return ("exact", exact_result)

    if relaxed_result:
        print(
            f"  ✅ RELAXED match found: '{target_number}' → '{relaxed_result}'",
            file=sys.stderr,
            flush=True,
        )
        return ("relaxed", relaxed_result)

    if numeric_result:
        print(
            f"  ✅ NUMERIC match found: '{target_number}' → '{numeric_result}'",
            file=sys.stderr,
            flush=True,
        )
        return ("numeric", numeric_result)

    print(
        f"  ❌ No match found for '{target_number}'",
        file=sys.stderr,
        flush=True,
    )
    return None


async def match_payments_concurrent(
    payment_invoice_numbers: List[str], invoice_numbers: List[str]
) -> List[Tuple[str, Optional[Tuple[str, str]]]]:
    """
    Match multiple payments to invoices using concurrent async matching.

    Args:
        payment_invoice_numbers: Invoice numbers from remittance
        invoice_numbers: Available invoice numbers from database

    Returns:
        List of tuples: (payment_invoice_number, match_result)
        where match_result is (match_type, matched_invoice) or None
    """
    print(
        f"🚀 Starting concurrent matching for {len(payment_invoice_numbers)} "
        f"payments against {len(invoice_numbers)} invoices",
        file=sys.stderr,
        flush=True,
    )

    # Build all lookup tables concurrently
    exact_task = asyncio.create_task(build_exact_lookup(invoice_numbers))
    relaxed_task = asyncio.create_task(build_relaxed_lookup(invoice_numbers))
    numeric_task = asyncio.create_task(build_numeric_lookup(invoice_numbers))

    exact_lookup, relaxed_lookup, numeric_lookup = await asyncio.gather(
        exact_task, relaxed_task, numeric_task
    )

    print(
        f"📊 Built lookups: exact={len(exact_lookup)}, "
        f"relaxed={len(relaxed_lookup)}, numeric={len(numeric_lookup)}",
        file=sys.stderr,
        flush=True,
    )

    # Match all payments concurrently
    match_tasks = [
        asyncio.create_task(
            find_best_match_concurrent(
                payment, exact_lookup, relaxed_lookup, numeric_lookup
            )
        )
        for payment in payment_invoice_numbers
    ]

    match_results = await asyncio.gather(*match_tasks)

    # Combine payment numbers with their match results
    results = list(zip(payment_invoice_numbers, match_results))

    # Log summary
    exact_count = sum(1 for _, result in results if result and result[0] == "exact")
    relaxed_count = sum(
        1 for _, result in results if result and result[0] == "relaxed"
    )  # noqa: E501
    numeric_count = sum(1 for _, result in results if result and result[0] == "numeric")
    no_match_count = sum(1 for _, result in results if result is None)

    print(
        f"🎉 Matching complete: {exact_count} exact, {relaxed_count} relaxed, "
        f"{numeric_count} numeric, {no_match_count} no match",
        file=sys.stderr,
        flush=True,
    )

    return results


# Legacy function for backwards compatibility - redirects to concurrent version
def find_potential_matches(
    target_number: str, lookup_table: dict[str, list[str]]
) -> list[tuple[str, str]]:
    """
    Legacy function - converts old format to new concurrent approach.
    This maintains backwards compatibility while using the new async system.
    """
    print(
        "⚠️ Using legacy find_potential_matches - "
        "consider migrating to match_payments_concurrent",
        file=sys.stderr,
        flush=True,
    )

    # Extract invoice numbers from the old combined lookup table
    invoice_numbers = []
    for matches in lookup_table.values():
        invoice_numbers.extend(matches)
    invoice_numbers = list(set(invoice_numbers))  # Remove duplicates

    # Run the new concurrent matcher
    async def run_match() -> Optional[Tuple[str, str]]:
        results = await match_payments_concurrent([target_number], invoice_numbers)
        return results[0][1]  # Return just the match result for this target

    # Run the async function synchronously for backwards compatibility
    result = asyncio.run(run_match())

    if result:
        match_type, matched_invoice = result
        return [(match_type, matched_invoice)]
    else:
        return []


def calculate_similarity_score(original: str, target: str) -> float:
    """
    Calculate similarity score between two invoice numbers.
    This is kept for backwards compatibility.
    """
    if original == target:
        return 1.0

    # Simple similarity based on common characters
    original_chars = set(original.lower())
    target_chars = set(target.lower())

    if not original_chars or not target_chars:
        return 0.0

    intersection = len(original_chars.intersection(target_chars))
    union = len(original_chars.union(target_chars))

    return intersection / union if union > 0 else 0.0
