# apps/api/src/domains/organizations/models.py
from typing import Optional

from pydantic import BaseModel


class OrganizationCreate(BaseModel):
    name: str


class OrganizationResponse(BaseModel):
    id: str
    name: str
    subscription_tier: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]


class CreateOrganizationResponse(BaseModel):
    organization: OrganizationResponse
    role: str


class OrganizationMemberResponse(BaseModel):
    id: str
    email: str
    display_name: Optional[str]
    role: str
    status: str
    joined_at: Optional[str]
    invited_by_email: Optional[str]
