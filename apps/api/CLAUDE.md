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
- `src/domains/` - Business domains (auth, invoices)
- `src/shared/` - Shared utilities and components
- `src/main.py` - FastAPI application entry point

### Key Business Domains
- **Authentication** (`/auth`) - User profiles, sessions, Supabase JWT integration
- **Invoices** (`/invoices`) - Invoice management with status workflows
- **Remittances** - Core remittance matching (AI-powered + manual overrides)
- **Organizations** - Multi-tenant organization support
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
- **Package Management**: Poetry for Python dependencies
- **Code Quality**: Black (88 char limit), isort, flake8, mypy (strict mode)

## Current State

### Known Issues
There are 16 lint issues documented in `lint-issues.md`:
- Missing `supabase` and `jwt` package dependencies
- Incorrect Prisma model references (`Profile` → `profiles`)
- Missing return type annotations on several functions
- References to non-existent `projects` domain

### API Structure
- Base URL: `/api/v1`
- Health check: `/health`
- Current endpoints: `/session` (auth), `/invoices`

## Development Notes

- Supabase local development stack runs on ports 54321-54327
- Prisma schema changes require running `prisma generate` before code changes
- All business logic should follow domain-driven design patterns
- Database operations use organization-scoped queries for multi-tenancy

### TYPE SAFETY FIRST ###
- This is a type-safe first project.
- Type annotations are required (enforced by mypy strict mode)
- NEVER use type ignore comments (# type: ignore) - always fix the underlying type issue properly
- NEVER use Any type.
- Where possible, types should be inherited/derived from prisma schema