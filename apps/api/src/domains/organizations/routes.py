# apps/api/src/domains/organizations/routes.py
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, status
from prisma.models import OrganizationMember, Profile

from prisma import Prisma
from src.core.database import get_db
from src.domains.auth.dependencies import get_current_profile
from src.domains.auth.models import SessionState
from src.domains.organizations.models import (
    CreateOrganizationResponse,
    OrganizationCreate,
    OrganizationMemberResponse,
    UpdateOrganizationMemberRequest,
)
from src.domains.organizations.service import OrganizationService
from src.shared.permissions import Permission, require_permission

# Add a prefix and tag to group this route clearly in OpenAPI
router = APIRouter(prefix="/organizations", tags=["Organizations"])


@router.put(
    "/",
    response_model=CreateOrganizationResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="createOrganization",
)
async def create_organization(
    organization_data: OrganizationCreate,
    profile: Profile = Depends(get_current_profile),
    db: Prisma = Depends(get_db),
) -> CreateOrganizationResponse:
    """
    Create a new organization and add the current user as owner.

    This endpoint is typically used when a user signs up directly and needs
    to create their first organization.
    """
    service = OrganizationService(db)
    return await service.create_organization(organization_data, profile)


@router.post("/switch/{org_id}", response_model=SessionState)
async def switch_organization(
    org_id: UUID,
    profile: Profile = Depends(get_current_profile),
    db: Prisma = Depends(get_db),
) -> SessionState:
    """
    Switch the user's active organization.

    This endpoint verifies the user is a member of the target organization
    and returns the updated session state for Zustand store updates.
    """
    service = OrganizationService(db)
    return await service.switch_organization(profile.id, str(org_id))


@router.get(
    "/{org_id}/members",
    response_model=List[OrganizationMemberResponse],
    operation_id="getOrganizationMembers",
)
async def get_organization_members(
    org_id: UUID,
    membership: OrganizationMember = Depends(
        require_permission(Permission.VIEW_MEMBERS)
    ),
    db: Prisma = Depends(get_db),
) -> List[OrganizationMemberResponse]:
    """
    Get all members of an organization.

    This endpoint returns detailed information about all active members
    of the organization. Access is restricted to users with VIEW_MEMBERS
    permission (typically owners, admins, and auditors).

    Returns:
        List of organization members with profile and invitation details
    """
    service = OrganizationService(db)
    return await service.get_organization_members(str(org_id))


@router.patch(
    "/{org_id}/members/{member_id}",
    response_model=OrganizationMemberResponse,
    operation_id="updateOrganizationMember",
)
async def update_organization_member(
    org_id: UUID,
    member_id: UUID,
    updates: UpdateOrganizationMemberRequest,
    membership: OrganizationMember = Depends(
        require_permission(Permission.MANAGE_MEMBERS)
    ),
    profile: Profile = Depends(get_current_profile),
    db: Prisma = Depends(get_db),
) -> OrganizationMemberResponse:
    """
    Update an organization member.

    This endpoint allows updating member status (e.g., soft deletion by setting
    status to 'removed'). Access is restricted to users with MANAGE_MEMBERS
    permission (typically owners and admins).

    Business rules:
    - Cannot remove yourself from the organization
    - Cannot remove the last owner (maintains organization access)
    - Can only remove active members

    Args:
        org_id: Organization ID
        member_id: Profile ID of the member to update
        updates: The updates to apply (currently supports status changes)

    Returns:
        Updated organization member details
    """
    service = OrganizationService(db)
    return await service.update_organization_member(
        str(org_id), str(member_id), updates, profile
    )
