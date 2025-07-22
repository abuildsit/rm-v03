# apps/api/src/domains/auth/dependencies.py
import jwt
from fastapi import Depends, Header, HTTPException, status
from jwt import PyJWKClient
from prisma.models import Profile

from prisma import Prisma
from src.core.database import get_db
from src.core.settings import settings
from src.shared.exceptions import UnlinkedProfileError

from .types import SupabaseJwtPayload

JWKS_URL = f"{settings.SUPABASE_URL}/auth/v1/jwks" if settings.SUPABASE_URL else None

_jwks_client = PyJWKClient(JWKS_URL) if JWKS_URL else None


def decode_supabase_jwt(token: str) -> SupabaseJwtPayload:
    """
    Verifies JWT token. Uses JWT_SECRET for development mode if available,
    otherwise falls back to Supabase JWKS for production.
    """
    # Development mode: prefer JWT_SECRET if available
    if settings.JWT_SECRET:
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET,
                algorithms=["HS256"],
                options={"verify_aud": False},
            )
            return SupabaseJwtPayload(**dict(payload))
        except jwt.PyJWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            )

    # Production mode: use Supabase JWKS
    if not _jwks_client:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Supabase not configured",
        )
    try:
        signing_key = _jwks_client.get_signing_key_from_jwt(token).key
        payload = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            options={"verify_aud": False},
        )
        # Create typed Pydantic model for JWT payload
        return SupabaseJwtPayload(**dict(payload))
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )


def get_auth_id(authorization: str = Header(None)) -> str:
    """
    Extracts and validates the Supabase JWT from the Authorization header.
    Returns the user's UUID (from the `sub` claim).
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token"
        )

    token = authorization.split(" ")[1]
    payload = decode_supabase_jwt(token)
    return payload.sub or ""


async def get_current_profile(
    auth_id: str = Depends(get_auth_id), db: Prisma = Depends(get_db)
) -> Profile:
    """
    Finds the linked profile for the authenticated user.
    """
    # Use direct dictionary for complex Prisma types to avoid TypedDict conflicts
    where_dict = {"authId": auth_id}
    include_dict = {"profile": True}
    link = await db.authlink.find_first(
        where=where_dict,  # type: ignore[arg-type]
        include=include_dict,  # type: ignore[arg-type]
    )
    if not link or not link.profile:
        raise UnlinkedProfileError()
    return link.profile
