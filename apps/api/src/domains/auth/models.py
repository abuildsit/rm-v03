# apps/api/src/domains/auth/models.py
from typing import List

from prisma.models import profiles
from pydantic import BaseModel


class PublicProfile(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    id: str
    name: str

    @classmethod
    def from_prisma(cls, profile: profiles) -> "PublicProfile":
        display_name = getattr(profile, "display_name", None)
        return cls(id=profile.id, name=display_name or profile.email)


class SessionPacket(BaseModel):
    user: PublicProfile
    non_db_related_list: List[str]
