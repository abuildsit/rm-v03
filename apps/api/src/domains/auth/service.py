from fastapi import HTTPException, status
from prisma.enums import MemberStatus
from prisma.models import OrganizationMember, Profile
from prisma.types import OrganizationMemberWhereInput

from prisma import Prisma
from src.domains.auth.models import OrganizationMembership, SessionState


class SessionService:
    """Service for session-related operations"""

    def __init__(self, db: Prisma):
        self.db = db

    async def get_session_state(self, profile: Profile) -> SessionState:
        """
        Get complete session state for a user including all organization memberships

        Args:
            profile: User's profile object

        Returns:
            SessionState with user info, current org, and all org memberships
        """
        try:
            # Get user's organization memberships with organization details
            memberships = await self.db.organizationmember.find_many(
                where={"profileId": profile.id, "status": MemberStatus.active},
                include={"organization": True},
            )

            organizations = []
            current_org_id = None
            current_org_name = None
            current_role = None
            current_subscription_tier = None

            # Process memberships
            if memberships:
                for membership in memberships:
                    if membership.organization:
                        organizations.append(
                            OrganizationMembership(
                                id=membership.organization.id,
                                name=membership.organization.name,
                                role=membership.role,
                            )
                        )

                        # Use last_accessed_org if available, otherwise use first org
                        if (
                            profile.lastAccessedOrgId
                            and profile.lastAccessedOrgId == membership.organization.id
                        ):
                            current_org_id = membership.organization.id
                            current_org_name = membership.organization.name
                            current_role = membership.role
                            current_subscription_tier = getattr(
                                membership.organization, "subscriptionTier", "basic"
                            )
                        elif current_org_id is None:
                            current_org_id = membership.organization.id
                            current_org_name = membership.organization.name
                            current_role = membership.role
                            current_subscription_tier = getattr(
                                membership.organization, "subscriptionTier", "basic"
                            )

            # Build session state
            return SessionState(
                user_id=profile.id,
                user_email=profile.email,
                user_display_name=getattr(profile, "displayName", None),
                organization_id=current_org_id,
                organization_name=current_org_name,
                role=current_role,
                subscription_tier=current_subscription_tier,
                active_remittance_id=None,  # TODO: Implement remittance selection
                organizations=organizations,
            )

        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error retrieving session state: {str(e)}",
            )


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
