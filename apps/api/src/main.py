from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.core.database import prisma
from src.domains.auth.routes import router as auth_router
from src.domains.bankaccounts.routes import router as bankaccounts_router
from src.domains.integrations.xero.auth.routes import router as xero_router
from src.domains.invoices.routes import router as invoices_router
from src.domains.organizations.routes import router as organizations_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Startup
    await prisma.connect()
    yield
    # Shutdown
    await prisma.disconnect()


app = FastAPI(
    title="RemitMatch API",
    description="API for remittance matching application",
    version="0.1.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router, prefix="/api/v1")
app.include_router(bankaccounts_router, prefix="/api/v1")
app.include_router(invoices_router, prefix="/api/v1")
app.include_router(organizations_router, prefix="/api/v1")
app.include_router(xero_router, prefix="/api/v1")


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "RemitMatch API is running"}


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "healthy"}
