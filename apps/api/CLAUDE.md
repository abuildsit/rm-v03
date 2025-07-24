# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

RemitMatch API - A FastAPI application for remittance matching and invoice processing with Supabase authentication and PostgreSQL database via Prisma ORM.

## Claude Behaviours:
- When asking design questions between options - give your opnion on the better approach, as well as the inherent trade-offs.

## Development Commands

### Core Development Tasks
```bash
make lint      # Run black, isort, flake8, and mypy
make format    # Run black and isort formatting only  
make check     # Run mypy type checking
make test      # Run pytest test suite
make security  # Run security scanning with bandit
make ci        # Full CI pipeline: generate Prisma client, lint, test
make dev       # Run development server in new terminal with timestamped logs (clears server.log)
make dev keep-log  # Run development server preserving existing logs (appends to server.log)
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
- **External Accounting** (`/external_accounting`) - Provider-agnostic accounting system integrations (Xero, future providers)
- **Remittances** (`/remittances`) - AI-powered remittance processing with three-tier matching (exact → relaxed → numeric) using async concurrent algorithms, with manual override capabilities

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

## Environment Configuration

### Required Settings
- `APP_BASE_URL` - Base URL for OAuth callbacks (default: http://localhost:8001)
- `FRONTEND_URL` - Frontend application URL for redirects
- `XERO_CLIENT_ID` - Xero OAuth application client ID
- `XERO_CLIENT_SECRET` - Xero OAuth application client secret
- `JWT_SECRET` - Secret for signing state tokens (minimum 32 characters)

### Supabase Settings
- `SUPABASE_URL` - Supabase project URL
- `SUPABASE_SERVICE_ROLE_KEY` - Service role key for admin operations
- `SUPABASE_ANON_KEY` - Anonymous key for client operations
- `DATABASE_URL` - PostgreSQL connection string

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

### Available Permissions
- **Organization**: `VIEW_MEMBERS`, `MANAGE_MEMBERS`, `EDIT_ORGANIZATION`, `MANAGE_BILLING`
- **Bank Accounts**: `VIEW_BANK_ACCOUNTS`, `MANAGE_BANK_ACCOUNTS`
- **Integrations**: `VIEW_INTEGRATIONS`, `MANAGE_INTEGRATIONS`
- **Invoices**: `VIEW_INVOICES`, `SYNC_INVOICES`
- **Payments**: `CREATE_PAYMENTS`

### Role Hierarchy
- **Owner**: Full access to all permissions
- **Admin**: Most permissions except billing management
- **Auditor**: Read-only access to members and bank accounts
- **User**: Basic view permissions only

## Current State

### Completed Features
- Xero OAuth authentication and connection management
- Provider-agnostic sync architecture with Xero implementation
- Invoice synchronization (AUTHORISED, VOIDED, DELETED statuses)
- Bank account synchronization  
- Background sync operations
- Comprehensive error handling and retry logic

### Active Development
- Enhanced remittance matching capabilities
- Advanced filtering and search features

### API Structure
- Base URL: `/api/v1`
- Health check: `/health`
- Current endpoints:
  - `/session` - Authentication and profile management
  - `/organizations/{org_id}/members` - Organization member management (requires VIEW_MEMBERS permission)
  - `/bankaccounts/{org_id}` - Bank account management (requires VIEW_BANK_ACCOUNTS/MANAGE_BANK_ACCOUNTS permissions)
  - `/invoices` - Invoice management
  - `/external-accounting/invoices/{org_id}` - Invoice sync (requires SYNC_INVOICES permission)
  - `/external-accounting/accounts/{org_id}` - Account sync (requires MANAGE_BANK_ACCOUNTS permission)

## Development Notes

- Supabase local development stack runs on ports 54321-54327
- Prisma schema changes require running `prisma generate` before code changes
- All business logic should follow domain-driven design patterns
- Database operations use organization-scoped queries for multi-tenancy
- Use shared permissions system for consistent authorization across domains
- All datetime operations must use timezone-aware objects (datetime.now(timezone.utc))
- The system handles provider-specific date formats automatically

### Development Server
- `make dev` starts the server in a new terminal window on http://0.0.0.0:8001
- All server output is logged to `server.log` with timestamps (YYYY-MM-DD HH:MM:SS format)
- Use `make dev keep-log` to preserve existing logs when restarting
- Server runs with auto-reload enabled for development

### Performance Considerations
- Sync operations run asynchronously to avoid blocking API responses
- Database upserts handle large datasets efficiently
- Provider rate limits are respected automatically
- Connection pooling via Prisma for optimal database performance

### DX
- After every implementations, run 'make ci' and report back to user on the outcome.

## External Accounting Integration Architecture

### Provider-Agnostic Design
The external accounting domain uses a clean abstraction layer to support multiple accounting providers:

- `src/domains/external_accounting/base/` - Provider-agnostic interfaces and logic
  - `BaseIntegrationDataService` - Abstract interface for all providers
  - `SyncOrchestrator` - Generic sync logic (database upserts, filtering)
  - `IntegrationFactory` - Provider resolution based on organization connections
  - `SyncResult` - Standard response model

- `src/domains/external_accounting/xero/` - Xero-specific implementation
  - `XeroDataService` - Implements BaseIntegrationDataService
  - `auth/` - OAuth flow management (existing)

### Usage Pattern
```python
# Get the right provider for an organization
factory = IntegrationFactory(db)
data_service = await factory.get_data_service(org_id)

# Use provider-agnostic interface
invoices = await data_service.get_invoices(org_id, filters)

# Or use orchestrator for sync + database operations
orchestrator = SyncOrchestrator(db)
result = await orchestrator.sync_invoices(data_service, org_id, options)
```

### Sync Operation Characteristics
- **Async Operations**: All syncs run in background tasks (non-blocking)
- **Rate Limiting**: Respects provider limits (Xero: 60 calls/min)
- **Pagination**: Handles large datasets (100 items/page)
- **Incremental Sync**: Supports both full and incremental synchronization
- **Error Handling**: Comprehensive retry logic with exponential backoff

### Xero-Specific Implementation Notes
- **Date Format Handling**: Automatically parses Xero's legacy `/Date(timestamp)/` format
- **API Query Syntax**: Handles Xero-specific DateTime and filter requirements
- **OAuth Integration**: Automatic initial sync triggered after successful connection
- **Token Management**: Automatic token refresh with connection status tracking

## Testing Strategy

- **Domain-focused testing**: Each domain has its own test suite in `tests/unit/domains/`
- **Shared component testing**: Shared utilities tested in `tests/unit/shared/`
- **Permission system coverage**: Comprehensive parametrized tests for all role/permission combinations
- **Route testing**: Focus on business logic, not permission system (tested separately)
- **Fixtures**: Domain-specific test fixtures in `tests/fixtures/`

### TYPE SAFETY FIRST ###
- This is a type-safe first project.
- Pydantic - not straight lists, etc from 'typing'
- Type annotations are required (enforced by mypy strict mode)
- NEVER use type ignore comments (# type: ignore) - always fix the underlying type issue properly
- NEVER use Any type.
- Where possible, types should be inherited/derived from prisma schema