from typing import Awaitable, Callable

from fastapi import Depends, HTTPException, status
from prisma.models import OrganizationMember, Profile

from prisma import Prisma
from src.core.database import get_db
from src.domains.auth.dependencies import get_current_profile
from src.domains.auth.service import validate_organization_access

from .models import Permission
from .services import has_permission


def require_permission(
    permission: Permission,
) -> Callable[..., Awaitable[OrganizationMember]]:
    """
    Dependency factory for role-based authorization.

    Creates a dependency that validates the current user has the specified
    permission for the organization.

    Args:
        permission: The permission required to access the endpoint

    Returns:
        Async dependency function that validates permission and returns membership
    """

    async def check_permission(
        org_id: str,
        profile: Profile = Depends(get_current_profile),
        db: Prisma = Depends(get_db),
    ) -> OrganizationMember:
        """
        Validate user has required permission for organization.

        Args:
            org_id: Organization ID from path parameter
            profile: Current user's profile
            db: Database connection

        Returns:
            OrganizationMember object if authorized

        Raises:
            HTTPException: If user lacks required permission
        """
        # Validate user has access to organization
        membership = await validate_organization_access(profile.id, org_id, db)

        # Check if user's role has the required permission
        if not has_permission(membership.role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions: {permission.value} required",
            )

        return membership

    return check_permission
