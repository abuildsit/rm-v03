# apps/api/src/domains/organizations/service.py
from typing import List

from fastapi import HTTPException, status
from prisma.enums import MemberStatus, OrganizationRole
from prisma.models import OrganizationMember, Profile

from prisma import Prisma
from src.domains.auth.models import SessionState
from src.domains.auth.service import SessionService, validate_organization_access
from src.domains.organizations.models import (
    CreateOrganizationResponse,
    OrganizationCreate,
    OrganizationMemberResponse,
    OrganizationResponse,
    UpdateOrganizationMemberRequest,
)


class OrganizationService:
    def __init__(self, db: Prisma):
        self.db = db

    async def create_organization(
        self, organization_data: OrganizationCreate, profile: Profile
    ) -> CreateOrganizationResponse:
        """
        Create a new organization and add the current user as owner.

        This method is typically used when a user signs up directly and needs
        to create their first organization.
        """
        # Create the organization
        organization = await self.db.organization.create(
            data={
                "name": organization_data.name,
                "subscriptionTier": "basic",
            }
        )

        # Add the current user as owner
        membership = await self.db.organizationmember.create(
            data={
                "profileId": profile.id,
                "organizationId": organization.id,
                "role": OrganizationRole.owner,
                "status": MemberStatus.active,
            }
        )

        # Convert to response format
        org_response = OrganizationResponse(
            id=organization.id,
            name=organization.name,
            subscription_tier=organization.subscriptionTier,
            created_at=(
                organization.createdAt.isoformat() if organization.createdAt else None
            ),
            updated_at=(
                organization.updatedAt.isoformat() if organization.updatedAt else None
            ),
        )

        return CreateOrganizationResponse(
            organization=org_response,
            role=membership.role,
        )

    async def switch_organization(
        self, profile_id: str, organization_id: str
    ) -> SessionState:
        """
        Switch the user's active organization.

        This method validates the user has access to the target organization,
        updates their last accessed organization, and returns the updated session state.
        """
        await validate_organization_access(profile_id, organization_id, self.db)

        await self.db.profile.update(
            where={"id": profile_id},
            data={"lastAccessedOrg": {"connect": {"id": organization_id}}},
        )

        updated_profile = await self.db.profile.find_unique(where={"id": profile_id})
        if not updated_profile:
            raise Exception("Profile not found after update")

        session_service = SessionService(self.db)
        return await session_service.get_session_state(updated_profile)

    async def get_organization_members(
        self, organization_id: str
    ) -> List[OrganizationMemberResponse]:
        """
        Get all members of an organization with detailed information.

        Args:
            organization_id: The organization ID to get members for

        Returns:
            List of organization members with profile and invitation details
        """
        members = await self.db.organizationmember.find_many(
            where={
                "organizationId": organization_id,
                "status": MemberStatus.active,
            },
            include={
                "profile": True,
                "invitedByProfile": True,
            },
            order={"joinedAt": "asc"},
        )

        member_responses = []
        for member in members:
            if member.profile:
                member_responses.append(
                    OrganizationMemberResponse(
                        id=member.profile.id,
                        email=member.profile.email,
                        display_name=member.profile.displayName,
                        role=member.role,
                        status=member.status,
                        joined_at=(
                            member.joinedAt.isoformat() if member.joinedAt else None
                        ),
                        invited_by_email=(
                            member.invitedByProfile.email
                            if member.invitedByProfile
                            else None
                        ),
                    )
                )

        return member_responses

    async def update_organization_member(
        self,
        organization_id: str,
        member_id: str,
        updates: UpdateOrganizationMemberRequest,
        requester_profile: Profile,
    ) -> OrganizationMemberResponse:
        """
        Update an organization member (e.g., soft delete by changing status).

        Args:
            organization_id: The organization ID
            member_id: The profile ID of the member to update
            updates: The updates to apply
            requester_profile: The profile making the request

        Returns:
            Updated organization member details

        Raises:
            HTTPException: If member not found or validation fails
        """
        # Fetch the member to update
        member = await self.db.organizationmember.find_first(
            where={
                "profileId": member_id,
                "organizationId": organization_id,
            },
            include={"profile": True},
        )

        if not member:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Member not found"
            )

        # Apply update-specific validations
        if updates.status == "removed":
            await self._validate_member_removal(
                member, requester_profile, organization_id
            )

        # Perform the update
        updated_member = await self.db.organizationmember.update(
            where={"id": member.id},
            data={"status": MemberStatus.removed},
            include={"profile": True, "invitedByProfile": True},
        )

        if not updated_member:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update member",
            )

        # Return formatted response
        return self._format_member_response(updated_member)

    async def _validate_member_removal(
        self,
        member: OrganizationMember,
        requester_profile: Profile,
        organization_id: str,
    ) -> None:
        """
        Validate that a member can be removed.

        Args:
            member: The member to be removed
            requester_profile: The profile making the request
            organization_id: The organization ID

        Raises:
            HTTPException: If validation fails
        """
        # Cannot remove yourself
        if member.profileId == requester_profile.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot remove yourself from the organization",
            )

        # Cannot remove last owner
        if member.role == OrganizationRole.owner:
            owner_count = await self.db.organizationmember.count(
                where={
                    "organizationId": organization_id,
                    "role": OrganizationRole.owner,
                    "status": MemberStatus.active,
                }
            )
            if owner_count <= 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot remove the last owner",
                )

        # Member must be active to be removed
        if member.status != MemberStatus.active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Member is not active"
            )

    def _format_member_response(
        self, member: OrganizationMember
    ) -> OrganizationMemberResponse:
        """
        Format a member database object into a response model.

        Args:
            member: Database member object with includes

        Returns:
            Formatted OrganizationMemberResponse
        """
        if not member.profile:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Member profile not found",
            )

        return OrganizationMemberResponse(
            id=member.profile.id,
            email=member.profile.email,
            display_name=member.profile.displayName,
            role=member.role,
            status=member.status,
            joined_at=(member.joinedAt.isoformat() if member.joinedAt else None),
            invited_by_email=(
                member.invitedByProfile.email if member.invitedByProfile else None
            ),
        )
