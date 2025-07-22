# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

RemitMatch API - A FastAPI application for remittance matching and invoice processing with Supabase authentication and PostgreSQL database via Prisma ORM.

## Development Commands

### Core Development Tasks
```bash
make lint      # Run black, isort, flake8, and mypy
make format    # Run black and isort formatting only  
make check     # Run mypy type checking
make test      # Run pytest test suite
```

### Database Operations
```bash
poetry run prisma generate  # Generate Prisma client after schema changes
poetry run prisma migrate   # Run database migrations
poetry run prisma db push   # Push schema changes to database
```

## Architecture

### Domain Structure
- `src/core/` - Application configuration, database setup, settings
- `src/domains/` - Business domains (auth, invoices, organizations, bankaccounts)
- `src/shared/` - Cross-domain shared components:
  - `permissions/` - Role-based permission system used across all domains
  - `exceptions/` - Common exception types and handlers
  - Additional utilities as needed
- `src/main.py` - FastAPI application entry point

### Key Business Domains
- **Authentication** (`/auth`) - User profiles, sessions, Supabase JWT integration
- **Organizations** (`/organizations`) - Multi-tenant organization support with role-based permissions
- **Bank Accounts** (`/bankaccounts`) - Bank account management and payment configuration
- **Invoices** (`/invoices`) - Invoice management with status workflows
- **Remittances** - Core remittance matching (AI-powered + manual overrides)
- **Xero Integration** - Accounting system sync

### Database Design
Multi-tenant PostgreSQL schema with:
- Organization-based data separation
- Comprehensive audit logging for all business actions
- Invoice status workflows (DRAFT → SUBMITTED → APPROVED → PAID)
- AI-powered remittance matching with manual override capabilities

## Technology Stack

- **Backend**: FastAPI 0.116.1 with Uvicorn ASGI server
- **Database**: PostgreSQL via Supabase with Prisma ORM (Python client 0.15.0)
- **Authentication**: Supabase Auth with JWT tokens (1-hour expiry)
- **Authorization**: Role-based permissions system with fine-grained access control
- **Package Management**: Poetry for Python dependencies
- **Code Quality**: Black (88 char limit), isort, flake8, mypy (strict mode)

## Permissions System

### Architecture
The application uses a centralized, role-based permission system located in `src/shared/permissions/`:

- **Permission Enum** (`models.py`): Defines all available permissions (e.g., `VIEW_MEMBERS`, `MANAGE_BANK_ACCOUNTS`)
- **Role Mappings** (`models.py`): Maps organization roles to sets of permissions
- **Permission Service** (`services.py`): Core logic for permission checking
- **Dependencies** (`dependencies.py`): FastAPI dependency factory for route protection

### Usage Pattern
```python
from src.shared.permissions import Permission, require_permission

@router.get("/{org_id}/resource")
async def get_resource(
    membership: OrganizationMember = Depends(
        require_permission(Permission.VIEW_RESOURCE)
    )
):
    # Route logic here - membership contains validated org access
    pass
```

### Role Hierarchy
- **Owner**: Full access to all permissions
- **Admin**: Most permissions except billing management
- **Auditor**: Read-only access to members and bank accounts
- **User**: Basic view permissions only

## Current State

### Known Issues
- Project is currently in active development
- Historical lint issues documented in `lint-issues.md` have been resolved (0 mypy issues as of last check)

### API Structure
- Base URL: `/api/v1`
- Health check: `/health`
- Current endpoints:
  - `/session` - Authentication and profile management
  - `/organizations/{org_id}/members` - Organization member management (requires VIEW_MEMBERS permission)
  - `/bankaccounts/{org_id}` - Bank account management (requires VIEW_BANK_ACCOUNTS/MANAGE_BANK_ACCOUNTS permissions)
  - `/invoices` - Invoice management

## Development Notes

- Supabase local development stack runs on ports 54321-54327
- Prisma schema changes require running `prisma generate` before code changes
- All business logic should follow domain-driven design patterns
- Database operations use organization-scoped queries for multi-tenancy
- Use shared permissions system for consistent authorization across domains

## Testing Strategy

- **Domain-focused testing**: Each domain has its own test suite in `tests/unit/domains/`
- **Shared component testing**: Shared utilities tested in `tests/unit/shared/`
- **Permission system coverage**: Comprehensive parametrized tests for all role/permission combinations
- **Route testing**: Focus on business logic, not permission system (tested separately)
- **Fixtures**: Domain-specific test fixtures in `tests/fixtures/`

### TYPE SAFETY FIRST ###
- This is a type-safe first project.
- Type annotations are required (enforced by mypy strict mode)
- NEVER use type ignore comments (# type: ignore) - always fix the underlying type issue properly
- NEVER use Any type.
- Where possible, types should be inherited/derived from prisma schema