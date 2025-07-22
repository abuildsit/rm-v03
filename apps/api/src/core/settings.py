from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    SUPABASE_URL: str | None = None
    SUPABASE_KEY: str | None = None
    DATABASE_URL: str | None = None
    # Additional environment variables that may be present
    supabase_service_role_key: str | None = None
    supabase_anon_key: str | None = None
    jwt_secret: str | None = None

    # Xero OAuth configuration
    XERO_CLIENT_ID: str | None = None
    XERO_CLIENT_SECRET: str | None = None
    XERO_REDIRECT_URI: str | None = None
    XERO_SCOPES: str = (
        "openid profile email accounting.transactions "
        "accounting.settings offline_access"
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
