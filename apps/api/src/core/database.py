# apps/api/src/core/database.py
from prisma import Prisma

# Global Prisma instance
prisma = Prisma()


async def get_db() -> Prisma:
    """Database dependency for FastAPI dependency injection."""
    return prisma
