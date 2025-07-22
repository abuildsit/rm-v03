from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class SyncResult(BaseModel):
    """Result of a sync operation."""

    object_type: str
    success: bool
    count: int
    duration_seconds: float
    last_modified: Optional[datetime] = None
    error: Optional[str] = None
