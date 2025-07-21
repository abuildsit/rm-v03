from fastapi import HTTPException, status
from gotrue.types import AuthResponse, User
from supabase import Client, create_client

from prisma import Prisma
from prisma.enums import MemberStatus
from prisma.models import OrganizationMember
from prisma.types import OrganizationMemberWhereInput
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
) -> OrganizationMember:
    """
    Validate that a user has access to an organization

    Args:
        profile_id: User's profile ID
        organization_id: Organization ID to check access for
        db: Prisma database connection

    Returns:
        OrganizationMember with role and membership details

    Raises:
        HTTPException: If user doesn't have access to organization
    """
    where_input: OrganizationMemberWhereInput = {
        "profileId": profile_id,
        "organizationId": organization_id,
        "status": MemberStatus.active,  # Only active members
    }
    membership = await db.organizationmember.find_first(where=where_input)

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to organization",
        )

    return membership
