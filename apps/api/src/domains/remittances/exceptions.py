"""
Domain-specific exceptions for remittances.
"""

from src.shared.exceptions import BaseHTTPException


class RemittanceException(BaseHTTPException):
    """Base exception for remittance-related errors."""

    status_code = 400


class RemittanceNotFoundError(RemittanceException):
    """Raised when a remittance is not found."""

    status_code = 404
    message = "Remittance not found"


class RemittanceLineNotFoundError(RemittanceException):
    """Raised when a remittance line is not found."""

    status_code = 404
    message = "Remittance line not found"


class InvalidFileFormatError(RemittanceException):
    """Raised when uploaded file has invalid format."""

    status_code = 400
    message = "Invalid file format. Only PDF files are supported."


class FileTooLargeError(RemittanceException):
    """Raised when uploaded file is too large."""

    status_code = 413
    message = "File too large. Maximum size is 10MB."


class RemittanceProcessingError(RemittanceException):
    """Raised when remittance processing fails."""

    status_code = 500
    message = "Failed to process remittance"


class ExtractionFailedError(RemittanceException):
    """Raised when AI extraction fails."""

    status_code = 500
    message = "Failed to extract data from remittance"


class MatchingFailedError(RemittanceException):
    """Raised when invoice matching fails."""

    status_code = 500
    message = "Failed to match invoices"


class InvalidRemittanceStateError(RemittanceException):
    """Raised when remittance is in invalid state for operation."""

    status_code = 400
    message = "Remittance is not in valid state for this operation"
