"""
AI-related exceptions for OpenAI integration.
"""


class AIException(Exception):
    """Base exception for AI-related errors."""

    pass


class AIRateLimitException(AIException):
    """Raised when API rate limits are exceeded."""

    pass


class AITimeoutException(AIException):
    """Raised when AI processing times out."""

    pass


class AIValidationException(AIException):
    """Raised when AI response validation fails."""

    pass


class AIConfigurationException(AIException):
    """Raised when AI configuration is invalid."""

    pass


class AIServiceUnavailableException(AIException):
    """Raised when AI service is temporarily unavailable."""

    pass
