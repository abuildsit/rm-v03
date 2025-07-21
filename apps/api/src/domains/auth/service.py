from fastapi import HTTPException, status
from gotrue.types import AuthResponse, User
from prisma.enums import MemberStatus
from prisma.models import organization_members
from prisma.types import organization_membersWhereInput
from supabase import Client, create_client

from prisma import Prisma
from src.core.settings import settings

supabase: Client | None = (
    create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
    if settings.SUPABASE_URL and settings.SUPABASE_KEY
    else None
)


def sign_up(email: str, password: str) -> AuthResponse:
    if not supabase:
        raise Exception("Supabase not configured")
    return supabase.auth.sign_up({"email": email, "password": password})


def sign_in(email: str, password: str) -> AuthResponse:
    if not supabase:
        raise Exception("Supabase not configured")
    return supabase.auth.sign_in_with_password({"email": email, "password": password})


def get_user(token: str) -> User | None:
    """Validates the JWT and returns the user."""
    if not supabase:
        return None
    session = supabase.auth.get_user(token)
    return session.user if session else None


async def validate_organization_access(
    profile_id: str, organization_id: str, db: Prisma
) -> organization_members:
    """
    Validate that a user has access to an organization

    Args:
        profile_id: User's profile ID
        organization_id: Organization ID to check access for
        db: Prisma database connection

    Returns:
        organization_members with role and membership details

    Raises:
        HTTPException: If user doesn't have access to organization
    """
    where_input: organization_membersWhereInput = {
        "profile_id": profile_id,
        "organization_id": organization_id,
        "status": MemberStatus.active,  # Only active members
    }
    membership = await db.organization_members.find_first(where=where_input)

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to organization",
        )

    return membership
