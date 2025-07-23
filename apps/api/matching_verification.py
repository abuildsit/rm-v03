#!/usr/bin/env python3
"""
Test script to verify the new async matching system works correctly.
"""
import asyncio
import os
import sys

# Must add path before importing
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

# Now import from the src path
from src.domains.remittances.matching.strategies import (  # noqa: E402
    match_payments_concurrent,
)


async def test_matching_types():
    """Test that all three match types work correctly."""
    print("🧪 Testing match types with the new async system")

    # Available invoices (simulated database)
    invoice_numbers = [
        "Invoice-Sarah-39859",  # Should match "39859" numerically (no collision)
        "INV 39832",  # Should match "INV39832" via relaxed
        "Inv--39791",  # Should match "INV39791" via relaxed
        "ABC-123-DEF",  # For testing numeric "123"
        "XYZ456QRS",  # For testing numeric "456"
        "EXACT-MATCH-001",  # For testing exact match
    ]

    # Test payments (search terms)
    test_payments = [
        "EXACT-MATCH-001",  # Should find exact match
        "39859",  # Should find numeric match with "Invoice-Sarah-39859"
        "INV39832",  # Should find relaxed match with "INV 39832"
        "INV39791",  # Should find relaxed match with "Inv--39791"
        "123",  # Should find numeric match with "ABC-123-DEF"
        "456",  # Should find numeric match with "XYZ456QRS"
        "NOMATCH99999",  # Should find no match
    ]

    print(
        f"📊 Testing with {len(invoice_numbers)} invoices and "
        f"{len(test_payments)} payments"
    )

    # Run the matching
    results = await match_payments_concurrent(test_payments, invoice_numbers)

    # Verify results
    print("\n🔍 MATCH RESULTS:")
    for payment, match_result in results:
        if match_result:
            match_type, matched_invoice = match_result
            print(f"  ✅ '{payment}' → '{matched_invoice}' ({match_type})")
        else:
            print(f"  ❌ '{payment}' → No match")

    # Verify specific expectations
    print("\n🔬 VERIFICATION:")
    expected_results = {
        "EXACT-MATCH-001": ("exact", "EXACT-MATCH-001"),
        "39859": ("numeric", "Invoice-Sarah-39859"),
        "INV39832": ("relaxed", "INV 39832"),
        "INV39791": ("relaxed", "Inv--39791"),
        "123": ("numeric", "ABC-123-DEF"),
        "456": ("numeric", "XYZ456QRS"),
        "NOMATCH99999": None,
    }

    all_correct = True
    for payment, match_result in results:
        expected = expected_results[payment]
        if expected is None:
            if match_result is None:
                print(f"  ✅ '{payment}' correctly found no match")
            else:
                print(f"  ❌ '{payment}' should have no match but found {match_result}")
                all_correct = False
        else:
            if match_result == expected:
                print(f"  ✅ '{payment}' correctly matched as {expected[0]}")
            else:
                print(f"  ❌ '{payment}' expected {expected} but got {match_result}")
                all_correct = False

    if all_correct:
        print("\n🎉 ALL TESTS PASSED! The async matching system is working correctly.")
        return True
    else:
        print("\n💥 SOME TESTS FAILED! The matching system needs debugging.")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_matching_types())
    sys.exit(0 if success else 1)
