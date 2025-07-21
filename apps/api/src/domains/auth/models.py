# apps/api/src/domains/auth/models.py
from typing import List, Optional

from pydantic import BaseModel


class OrganizationMembership(BaseModel):
    id: str
    name: str
    role: str


class SessionState(BaseModel):
    user_id: str
    user_email: str
    user_display_name: Optional[str]
    organization_id: Optional[str]
    organization_name: Optional[str]
    role: Optional[str]
    subscription_tier: Optional[str]
    active_remittance_id: Optional[str]
    organizations: List[OrganizationMembership]
