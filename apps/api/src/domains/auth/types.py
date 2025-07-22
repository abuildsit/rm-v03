"""Auth domain type definitions for type safety."""

from typing import Literal, Optional

from pydantic import BaseModel, Field


class SupabaseJwtPayload(BaseModel):
    """Supabase JWT token payload structure."""

    # Standard JWT claims
    sub: Optional[str] = Field(None, description="Subject (user ID)")
    iss: Optional[str] = Field(None, description="Token issuer")
    aud: Optional[str | list[str]] = Field(None, description="Token audience")
    exp: Optional[int] = Field(None, description="Expiration timestamp")
    iat: Optional[int] = Field(None, description="Issued at timestamp")
    nbf: Optional[int] = Field(None, description="Not before timestamp")
    jti: Optional[str] = Field(None, description="JWT ID")

    # Supabase-specific claims
    email: Optional[str] = Field(None, description="User email address")
    email_verified: Optional[bool] = Field(
        None, description="Whether email is verified"
    )
    phone: Optional[str] = Field(None, description="User phone number")
    phone_verified: Optional[bool] = Field(
        None, description="Whether phone is verified"
    )
    role: Optional[Literal["authenticated", "anon", "service_role"]] = Field(
        None, description="User role"
    )
    app_metadata: Optional[dict[str, str | int | bool | list[str] | None]] = Field(
        None, description="Application metadata"
    )
    user_metadata: Optional[dict[str, str | int | bool | list[str] | None]] = Field(
        None, description="User metadata"
    )

    # Session information
    session_id: Optional[str] = Field(None, description="Session identifier")
    is_anonymous: Optional[bool] = Field(None, description="Whether user is anonymous")

    model_config = {"extra": "allow"}
