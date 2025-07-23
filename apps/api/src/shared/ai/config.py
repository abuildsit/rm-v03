"""
AI configuration settings and constants.
"""

from dataclasses import dataclass

from src.core.settings import settings

# Using Python 3.12+ type hints


@dataclass
class AIConfig:
    """Configuration for AI services."""

    # OpenAI settings
    api_key: str
    model: str = "gpt-4-turbo-preview"
    max_tokens: int = 4000
    timeout: int = 300  # 5 minutes
    max_retries: int = 3

    # Rate limiting
    requests_per_minute: int = 60
    requests_per_day: int = 10000

    # Assistant settings
    assistant_id: str | None = None

    @classmethod
    def from_settings(cls) -> "AIConfig":
        """Create AIConfig from application settings."""
        if not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is required")

        return cls(
            api_key=settings.OPENAI_API_KEY,
            model=settings.OPENAI_MODEL,
            max_tokens=settings.OPENAI_MAX_TOKENS,
            timeout=settings.OPENAI_TIMEOUT,
            max_retries=settings.OPENAI_MAX_RETRIES,
            assistant_id=settings.OPENAI_ASSISTANT_ID,
        )

    def to_openai_kwargs(self) -> dict[str, str | int]:
        """Convert to OpenAI client kwargs."""
        return {
            "api_key": self.api_key,
            "timeout": self.timeout,
            "max_retries": self.max_retries,
        }


# Default configuration from settings
try:
    ai_config: AIConfig | None = AIConfig.from_settings()
except ValueError:
    # If no API key is provided, create empty config
    ai_config = None
