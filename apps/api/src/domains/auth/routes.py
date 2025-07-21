# apps/api/src/domains/auth/routes.py
from fastapi import APIRouter, Depends
from prisma.models import profiles

from prisma import Prisma
from src.core.database import get_db
from src.domains.auth.dependencies import get_current_profile
from src.domains.auth.models import PublicProfile, SessionPacket

# Add a prefix and tag to group this route clearly in OpenAPI
router = APIRouter(prefix="/session", tags=["Sessions"])


@router.get(
    "",
    response_model=SessionPacket,
    operation_id="getSession",  # Explicit, clean function name for Orval
)
async def get_session(
    db: Prisma = Depends(get_db), profile: profiles = Depends(get_current_profile)
) -> SessionPacket:

    return SessionPacket(
        user=PublicProfile.from_prisma(profile),
        non_db_related_list=["a", "b", "c"],
    )
