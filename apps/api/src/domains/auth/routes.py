# apps/api/src/domains/auth/routes.py
from fastapi import APIRouter, Depends
from prisma.models import Profile

from prisma import Prisma
from src.core.database import get_db
from src.domains.auth.dependencies import get_current_profile
from src.domains.auth.models import SessionState
from src.domains.auth.service import SessionService

# Add a prefix and tag to group this route clearly in OpenAPI
router = APIRouter(prefix="/session", tags=["Sessions"])


@router.get(
    "",
    response_model=SessionState,
    operation_id="getSessionState",  # Explicit, clean function name for Orval
)
async def get_session_state(
    profile: Profile = Depends(get_current_profile), db: Prisma = Depends(get_db)
) -> SessionState:
    service = SessionService(db)
    return await service.get_session_state(profile)
