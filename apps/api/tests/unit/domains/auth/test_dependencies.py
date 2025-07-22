"""
Tests for authentication dependencies in src/domains/auth/dependencies.py

Tests the core JWT validation and profile resolution functionality.
"""

from unittest.mock import Mock, patch

import jwt
import pytest
from fastapi import HTTPException

from src.domains.auth.dependencies import (
    decode_supabase_jwt,
    get_auth_id,
    get_current_profile,
)
from src.shared.exceptions import UnlinkedProfileError


class TestDecodeSupabaseJWT:
    """Test JWT token validation with both development and production modes."""

    def test_valid_development_jwt_token(
        self, test_jwt_secret: str, valid_jwt_payload: dict
    ):
        """Test successful JWT validation in development mode (JWT_SECRET)."""
        # Generate valid token
        token = jwt.encode(valid_jwt_payload, test_jwt_secret, algorithm="HS256")

        # Mock settings to use JWT_SECRET
        with patch(
            "src.domains.auth.dependencies.settings.JWT_SECRET", test_jwt_secret
        ):
            result = decode_supabase_jwt(token)

        assert result.sub == "test-user-id-123"
        assert result.email == "test@example.com"
        assert result.aud == "authenticated"
        assert result.iss == "supabase"

    def test_invalid_token_signature_raises_401(self, test_jwt_secret: str):
        """Test that invalid token signature raises 401."""
        # Create token with wrong secret
        invalid_token = jwt.encode({"sub": "test"}, "wrong-secret", algorithm="HS256")

        with patch(
            "src.domains.auth.dependencies.settings.JWT_SECRET", test_jwt_secret
        ):
            with pytest.raises(HTTPException) as exc_info:
                decode_supabase_jwt(invalid_token)

        assert exc_info.value.status_code == 401
        assert "Invalid or expired token" in exc_info.value.detail

    def test_malformed_jwt_raises_401(self, test_jwt_secret: str):
        """Test that malformed JWT raises 401."""
        malformed_token = "not.a.valid.jwt.token"

        with patch(
            "src.domains.auth.dependencies.settings.JWT_SECRET", test_jwt_secret
        ):
            with pytest.raises(HTTPException) as exc_info:
                decode_supabase_jwt(malformed_token)

        assert exc_info.value.status_code == 401
        assert "Invalid or expired token" in exc_info.value.detail

    def test_fallback_to_jwks_when_no_secret(self):
        """Test fallback to JWKS mode when JWT_SECRET not available."""
        token = "test.jwt.token"

        # Mock no JWT_SECRET and no JWKS client
        with (
            patch("src.domains.auth.dependencies.settings.JWT_SECRET", None),
            patch("src.domains.auth.dependencies._jwks_client", None),
        ):
            with pytest.raises(HTTPException) as exc_info:
                decode_supabase_jwt(token)

        assert exc_info.value.status_code == 500
        assert "Supabase not configured" in exc_info.value.detail


class TestGetAuthId:
    """Test auth ID extraction from Authorization header."""

    def test_extract_auth_id_from_valid_bearer_token(self, valid_jwt_token: str):
        """Test successful auth ID extraction from valid Bearer token."""
        authorization = f"Bearer {valid_jwt_token}"

        with patch("src.domains.auth.dependencies.decode_supabase_jwt") as mock_decode:
            from src.domains.auth.types import SupabaseJwtPayload

            mock_decode.return_value = SupabaseJwtPayload(
                sub="test-user-id-123",
                email="test@example.com",
            )

            result = get_auth_id(authorization)

        assert result == "test-user-id-123"
        mock_decode.assert_called_once_with(valid_jwt_token)

    def test_missing_authorization_header_raises_401(self):
        """Test that missing Authorization header raises 401."""
        with pytest.raises(HTTPException) as exc_info:
            get_auth_id(None)

        assert exc_info.value.status_code == 401
        assert "Missing token" in exc_info.value.detail

    def test_invalid_bearer_format_raises_401(self):
        """Test that invalid Bearer format raises 401."""
        invalid_headers = [
            "InvalidFormat token",
            "Bearer",  # Missing token
            "Basic dGVzdA==",  # Wrong auth type
            "",  # Empty string
        ]

        for invalid_header in invalid_headers:
            with pytest.raises(HTTPException) as exc_info:
                get_auth_id(invalid_header)

            assert exc_info.value.status_code == 401
            assert "Missing token" in exc_info.value.detail

    def test_empty_sub_claim_returns_empty_string(self, valid_jwt_token: str):
        """Test handling of empty sub claim."""
        authorization = f"Bearer {valid_jwt_token}"

        with patch("src.domains.auth.dependencies.decode_supabase_jwt") as mock_decode:
            from src.domains.auth.types import SupabaseJwtPayload

            mock_decode.return_value = SupabaseJwtPayload(
                sub=None, email="test@example.com"
            )

            result = get_auth_id(authorization)

        assert result == ""


class TestGetCurrentProfile:
    """Test profile resolution from auth_id via auth_links."""

    @pytest.mark.asyncio
    async def test_valid_auth_id_returns_profile(
        self, mock_auth_link_with_profile: Mock, mock_prisma: Mock
    ):
        """Test successful profile retrieval with valid auth_id."""
        auth_id = "test-user-id-123"

        # Mock database call
        mock_prisma.authlink.find_first.return_value = mock_auth_link_with_profile

        result = await get_current_profile(auth_id, mock_prisma)

        assert result == mock_auth_link_with_profile.profile
        mock_prisma.authlink.find_first.assert_called_once()

        # Verify the where clause was constructed correctly
        call_args = mock_prisma.authlink.find_first.call_args
        assert call_args[1]["where"]["authId"] == auth_id
        assert call_args[1]["include"]["profile"] is True

    @pytest.mark.asyncio
    async def test_nonexistent_auth_id_raises_unlinked_profile_error(
        self, mock_prisma: Mock
    ):
        """Test that nonexistent auth_id raises UnlinkedProfileError."""
        auth_id = "nonexistent-auth-id"

        # Mock no auth link found
        mock_prisma.authlink.find_first.return_value = None

        with pytest.raises(UnlinkedProfileError):
            await get_current_profile(auth_id, mock_prisma)

    @pytest.mark.asyncio
    async def test_auth_link_without_profile_raises_unlinked_profile_error(
        self, mock_auth_link: Mock, mock_prisma: Mock
    ):
        """Test that auth link without profile raises UnlinkedProfileError."""
        auth_id = "test-user-id-123"

        # Mock auth link found but no profile attached
        mock_auth_link.profile = None
        mock_prisma.authlink.find_first.return_value = mock_auth_link

        with pytest.raises(UnlinkedProfileError):
            await get_current_profile(auth_id, mock_prisma)
