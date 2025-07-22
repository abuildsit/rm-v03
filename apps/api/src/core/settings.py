from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Supabase configuration
    SUPABASE_URL: str | None = None
    SUPABASE_KEY: str | None = None
    DATABASE_URL: str | None = None
    SUPABASE_SERVICE_ROLE_KEY: str | None = None
    SUPABASE_ANON_KEY: str | None = None
    JWT_SECRET: str | None = None

    # Application URLs
    APP_BASE_URL: str = "http://localhost:8001"  # Default for development
    FRONTEND_URL: str | None = None

    # Xero OAuth configuration
    XERO_CLIENT_ID: str | None = None
    XERO_CLIENT_SECRET: str | None = None
    XERO_SCOPES: str = (
        "openid profile email accounting.transactions "
        "accounting.settings offline_access"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )


settings = Settings()
