"""
RemitMatch AI Response Validation - Implementation Examples
==========================================================

This file demonstrates the validation patterns used in RemitMatch
for ensuring AI extraction results meet business requirements.
"""

import logging
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, ValidationError


class ValidationResult(BaseModel):
    """Result of validation check"""

    is_valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class RemittanceValidationResult(BaseModel):
    """Complete validation result for remittance extraction"""

    is_valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)

    # Additional validation metrics
    total_amount_variance: Optional[Decimal] = None
    duplicate_invoices: List[str] = Field(default_factory=list)
    invalid_amounts: List[str] = Field(default_factory=list)


class AIExtractedPayment(BaseModel):
    """Individual payment validation model"""

    InvoiceNo: str = Field(
        ..., min_length=1, description="Invoice number must not be empty"
    )
    PaidAmount: Decimal = Field(..., gt=0, description="Amount must be positive")


class AIExtractionResult(BaseModel):
    """AI extraction result with validation"""

    Date: Optional[str] = Field(None, description="Payment date")
    TotalAmount: Decimal = Field(..., gt=0, description="Total amount must be positive")
    PaymentReference: Optional[str] = Field(None, description="Payment reference")
    Payments: List[AIExtractedPayment] = Field(
        ..., min_items=1, description="At least one payment required"
    )
    confidence: Decimal = Field(..., ge=0, le=1, description="Confidence must be 0-1")


class ValidationService:
    """
    Service for validating AI extraction results against business rules.

    This service implements comprehensive validation including:
    - Data consistency checks
    - Business rule validation
    - Amount reconciliation
    - Format validation
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)

        # Validation thresholds
        self.min_confidence_threshold = Decimal("0.3")
        self.amount_variance_threshold = Decimal("0.01")  # 1 cent tolerance
        self.max_invoice_number_length = 50
        self.min_total_amount = Decimal("0.01")
        self.max_total_amount = Decimal("999999.99")

    async def validate_ai_extraction_result(
        self, extraction_result: AIExtractionResult, org_context: Dict[str, Any]
    ) -> RemittanceValidationResult:
        """
        Comprehensive validation of AI extraction results.

        Args:
            extraction_result: AI extraction result to validate
            org_context: Organization context for logging

        Returns:
            RemittanceValidationResult with detailed validation outcome
        """
        errors = []
        warnings = []

        try:
            # 1. Basic data validation
            basic_validation = self._validate_basic_data(extraction_result)
            errors.extend(basic_validation.errors)
            warnings.extend(basic_validation.warnings)

            # 2. Amount consistency validation
            amount_validation = self._validate_amount_consistency(extraction_result)
            errors.extend(amount_validation.errors)
            warnings.extend(amount_validation.warnings)

            # 3. Payment validation
            payment_validation = self._validate_payments(extraction_result.Payments)
            errors.extend(payment_validation.errors)
            warnings.extend(payment_validation.warnings)

            # 4. Date validation
            date_validation = self._validate_date_format(extraction_result.Date)
            errors.extend(date_validation.errors)
            warnings.extend(date_validation.warnings)

            # 5. Confidence validation
            confidence_validation = self._validate_confidence_score(
                extraction_result.confidence
            )
            errors.extend(confidence_validation.errors)
            warnings.extend(confidence_validation.warnings)

            # 6. Business rule validation
            business_validation = self._validate_business_rules(extraction_result)
            errors.extend(business_validation.errors)
            warnings.extend(business_validation.warnings)

            # Calculate additional metrics
            total_amount_variance = self._calculate_amount_variance(extraction_result)
            duplicate_invoices = self._find_duplicate_invoices(
                extraction_result.Payments
            )
            invalid_amounts = self._find_invalid_amounts(extraction_result.Payments)

            result = RemittanceValidationResult(
                is_valid=len(errors) == 0,
                errors=errors,
                warnings=warnings,
                total_amount_variance=total_amount_variance,
                duplicate_invoices=duplicate_invoices,
                invalid_amounts=invalid_amounts,
            )

            self.logger.info(
                f"Validation completed: {'VALID' if result.is_valid else 'INVALID'}"
            )
            if errors:
                self.logger.warning(f"Validation errors: {errors}")

            return result

        except Exception as e:
            self.logger.error(f"Validation service error: {str(e)}")
            return RemittanceValidationResult(
                is_valid=False, errors=[f"Validation service error: {str(e)}"]
            )

    def _validate_basic_data(
        self, extraction_result: AIExtractionResult
    ) -> ValidationResult:
        """Validate basic data requirements"""
        errors = []
        warnings = []

        # Check if payments exist
        if not extraction_result.Payments:
            errors.append("No payments extracted from document")

        # Check total amount bounds
        if extraction_result.TotalAmount < self.min_total_amount:
            errors.append(f"Total amount too small: ${extraction_result.TotalAmount}")
        elif extraction_result.TotalAmount > self.max_total_amount:
            errors.append(f"Total amount too large: ${extraction_result.TotalAmount}")

        # Check for payment reference
        if not extraction_result.PaymentReference:
            warnings.append(
                "No payment reference found - manual verification may be needed"
            )

        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings
        )

    def _validate_amount_consistency(
        self, extraction_result: AIExtractionResult
    ) -> ValidationResult:
        """Validate amount consistency between total and individual payments"""
        errors = []
        warnings = []

        if not extraction_result.Payments:
            return ValidationResult(is_valid=True, errors=errors, warnings=warnings)

        # Calculate sum of individual payments
        calculated_total = sum(
            payment.PaidAmount for payment in extraction_result.Payments
        )
        variance = abs(calculated_total - extraction_result.TotalAmount)

        if variance > self.amount_variance_threshold:
            errors.append(
                f"Amount mismatch: Total ${extraction_result.TotalAmount} "
                f"vs calculated ${calculated_total} (variance: ${variance})"
            )
        elif variance > Decimal("0"):
            warnings.append(f"Minor amount variance: ${variance}")

        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings
        )

    def _validate_payments(
        self, payments: List[AIExtractedPayment]
    ) -> ValidationResult:
        """Validate individual payment data"""
        errors = []
        warnings = []

        for i, payment in enumerate(payments):
            payment_prefix = f"Payment {i+1}"

            # Invoice number validation
            if not payment.InvoiceNo or not payment.InvoiceNo.strip():
                errors.append(f"{payment_prefix}: Empty invoice number")
            elif len(payment.InvoiceNo) > self.max_invoice_number_length:
                errors.append(
                    f"{payment_prefix}: Invoice number too long ({len(payment.InvoiceNo)} chars)"
                )

            # Amount validation
            if payment.PaidAmount <= 0:
                errors.append(f"{payment_prefix}: Invalid amount ${payment.PaidAmount}")
            elif payment.PaidAmount > self.max_total_amount:
                errors.append(
                    f"{payment_prefix}: Amount too large ${payment.PaidAmount}"
                )

            # Format validation
            if payment.InvoiceNo and not self._is_valid_invoice_format(
                payment.InvoiceNo
            ):
                warnings.append(
                    f"{payment_prefix}: Unusual invoice number format: {payment.InvoiceNo}"
                )

        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings
        )

    def _validate_date_format(self, date_str: Optional[str]) -> ValidationResult:
        """Validate payment date format"""
        errors = []
        warnings = []

        if not date_str:
            warnings.append("No payment date extracted")
            return ValidationResult(is_valid=True, errors=errors, warnings=warnings)

        try:
            # Try parsing as ISO date
            parsed_date = datetime.fromisoformat(date_str.replace("Z", "+00:00")).date()

            # Check if date is reasonable (not too far in future/past)
            today = date.today()
            if parsed_date > today:
                warnings.append(f"Future payment date: {date_str}")
            elif (today - parsed_date).days > 365:
                warnings.append(f"Payment date over a year old: {date_str}")

        except (ValueError, TypeError) as e:
            errors.append(f"Invalid date format: {date_str}")

        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings
        )

    def _validate_confidence_score(self, confidence: Decimal) -> ValidationResult:
        """Validate AI confidence score"""
        errors = []
        warnings = []

        if confidence < 0 or confidence > 1:
            errors.append(f"Invalid confidence score: {confidence} (must be 0-1)")
        elif confidence < self.min_confidence_threshold:
            warnings.append(f"Low confidence score: {confidence}")

        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings
        )

    def _validate_business_rules(
        self, extraction_result: AIExtractionResult
    ) -> ValidationResult:
        """Apply organization-specific business rules"""
        errors = []
        warnings = []

        # Example business rules - customize based on requirements

        # Rule: Maximum 20 payments per remittance
        if len(extraction_result.Payments) > 20:
            errors.append(
                f"Too many payments: {len(extraction_result.Payments)} (max 20)"
            )

        # Rule: Total amount over $10,000 requires manual verification
        if extraction_result.TotalAmount > Decimal("10000.00"):
            warnings.append(
                f"Large amount requires verification: ${extraction_result.TotalAmount}"
            )

        # Rule: Check for common invoice number patterns
        invoice_numbers = [p.InvoiceNo for p in extraction_result.Payments]
        if len(set(invoice_numbers)) != len(invoice_numbers):
            duplicates = [
                inv for inv in invoice_numbers if invoice_numbers.count(inv) > 1
            ]
            errors.append(f"Duplicate invoice numbers found: {list(set(duplicates))}")

        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings
        )

    def _calculate_amount_variance(
        self, extraction_result: AIExtractionResult
    ) -> Decimal:
        """Calculate variance between total and sum of payments"""
        if not extraction_result.Payments:
            return Decimal("0")

        calculated_total = sum(
            payment.PaidAmount for payment in extraction_result.Payments
        )
        return abs(calculated_total - extraction_result.TotalAmount)

    def _find_duplicate_invoices(self, payments: List[AIExtractedPayment]) -> List[str]:
        """Find duplicate invoice numbers"""
        invoice_counts = {}
        for payment in payments:
            invoice_counts[payment.InvoiceNo] = (
                invoice_counts.get(payment.InvoiceNo, 0) + 1
            )

        return [invoice for invoice, count in invoice_counts.items() if count > 1]

    def _find_invalid_amounts(self, payments: List[AIExtractedPayment]) -> List[str]:
        """Find payments with invalid amounts"""
        invalid = []
        for payment in payments:
            if payment.PaidAmount <= 0 or payment.PaidAmount > self.max_total_amount:
                invalid.append(f"{payment.InvoiceNo}: ${payment.PaidAmount}")
        return invalid

    def _is_valid_invoice_format(self, invoice_no: str) -> bool:
        """Check if invoice number follows common patterns"""
        # Common patterns: INV-123, BILL/456, 789, etc.
        # This is a simplified check - customize based on your formats

        # Check for reasonable length
        if len(invoice_no) > 50:
            return False

        # Check for printable characters only
        if not invoice_no.isprintable():
            return False

        # Check for common patterns (customize as needed)
        import re

        patterns = [
            r"^[A-Za-z]*-?\d+$",  # Letters followed by optional dash and numbers
            r"^\d+$",  # Pure numbers
            r"^[A-Za-z]+/\d+$",  # Letters slash numbers
            r"^[A-Za-z]+\d+$",  # Letters and numbers
        ]

        return any(re.match(pattern, invoice_no.strip()) for pattern in patterns)


# Custom validation decorators and utilities
def validate_extraction_result(func):
    """Decorator to automatically validate extraction results"""

    async def wrapper(*args, **kwargs):
        result = await func(*args, **kwargs)

        if isinstance(result, AIExtractionResult):
            validation_service = ValidationService()
            validation = await validation_service.validate_ai_extraction_result(
                result, kwargs.get("org_context", {})
            )

            if not validation.is_valid:
                raise ValidationError(f"Validation failed: {validation.errors}")

        return result

    return wrapper


# Example usage and testing
async def example_validation():
    """Example of how to use the validation service"""

    # Create sample extraction result
    sample_result = AIExtractionResult(
        Date="2024-01-15",
        TotalAmount=Decimal("1250.00"),
        PaymentReference="REF-123456",
        Payments=[
            AIExtractedPayment(InvoiceNo="INV-001", PaidAmount=Decimal("500.00")),
            AIExtractedPayment(InvoiceNo="INV-002", PaidAmount=Decimal("750.00")),
        ],
        confidence=Decimal("0.85"),
    )

    # Initialize validation service
    validation_service = ValidationService()

    # Perform validation
    org_context = {"organisation_id": "test-org"}
    validation_result = await validation_service.validate_ai_extraction_result(
        sample_result, org_context
    )

    # Display results
    print(f"Validation Result: {'VALID' if validation_result.is_valid else 'INVALID'}")

    if validation_result.errors:
        print("Errors:")
        for error in validation_result.errors:
            print(f"  - {error}")

    if validation_result.warnings:
        print("Warnings:")
        for warning in validation_result.warnings:
            print(f"  - {warning}")

    print(f"Amount variance: ${validation_result.total_amount_variance}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(example_validation())
