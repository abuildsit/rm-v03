# Permissions System Documentation (TEMP)

## Overview
The RemitMatch API uses a centralized, role-based permission system located in `src/shared/permissions/` to control access to resources across all domains.

## Permission Categories

### Organization Management
| Permission | Value | Description | Available to Roles |
|------------|-------|-------------|-------------------|
| `VIEW_MEMBERS` | `view_members` | View organization member list and details | Owner, Admin, Auditor |
| `MANAGE_MEMBERS` | `manage_members` | Add, remove, update member roles | Owner, Admin |
| `MANAGE_BILLING` | `manage_billing` | Update billing settings and payment methods | Owner only |
| `EDIT_ORGANIZATION` | `edit_organization` | Update organization profile and settings | Owner, Admin |

### Bank Account Management
| Permission | Value | Description | Available to Roles |
|------------|-------|-------------|-------------------|
| `VIEW_BANK_ACCOUNTS` | `view_bank_accounts` | View bank account details | Owner, Admin, Auditor, User |
| `MANAGE_BANK_ACCOUNTS` | `manage_bank_accounts` | Update bank account settings | Owner, Admin |

### Integration Management
| Permission | Value | Description | Available to Roles |
|------------|-------|-------------|-------------------|
| `VIEW_INTEGRATIONS` | `view_integrations` | View integration connection status | Owner, Admin, Auditor |
| `MANAGE_INTEGRATIONS` | `manage_integrations` | Connect/disconnect integrations | Owner, Admin |

### Invoice Management
| Permission | Value | Description | Available to Roles |
|------------|-------|-------------|-------------------|
| `VIEW_INVOICES` | `view_invoices` | View invoice list and details | Owner, Admin, Auditor |
| `SYNC_INVOICES` | `sync_invoices` | Trigger invoice synchronization | Owner, Admin |

### Payment Management
| Permission | Value | Description | Available to Roles |
|------------|-------|-------------|-------------------|
| `CREATE_PAYMENTS` | `create_payments` | Create payments in accounting system (future use) | Owner, Admin |

### Remittance Management
| Permission | Value | Description | Available to Roles |
|------------|-------|-------------|-------------------|
| `VIEW_REMITTANCES` | `view_remittances` | View remittance list and details | Owner, Admin, Auditor, User |
| `CREATE_REMITTANCES` | `create_remittances` | Upload new remittances | Owner, Admin, User |
| `MANAGE_REMITTANCES` | `manage_remittances` | Update remittance details | Owner, Admin |
| `APPROVE_REMITTANCES` | `approve_remittances` | Approve remittance matches | Owner, Admin |

## Role Hierarchy

### Owner
- **Full Access**: Has all permissions in the system
- **Key Capabilities**: Can manage billing, all organization settings, and all business operations
- **Unique Permissions**: `MANAGE_BILLING` (only role with billing access)

### Admin  
- **Near Full Access**: Has all permissions except billing management
- **Key Capabilities**: Can manage members, bank accounts, integrations, and all business operations
- **Restrictions**: Cannot manage billing settings

### Auditor
- **Read-Only Access**: Can view all resources but cannot modify anything
- **Key Capabilities**: View members, bank accounts, integrations, invoices, and remittances
- **Use Case**: Compliance, reporting, and oversight roles

### User
- **Limited Access**: Basic operational permissions
- **Key Capabilities**: View bank accounts, view and create remittances
- **Restrictions**: Cannot view organization members, manage settings, or approve remittances

## Implementation Architecture

### Core Components
- **Permission Enum** (`models.py`): Defines all available permissions with descriptive comments
- **Role Mappings** (`models.py`): Maps organization roles to sets of permissions via `ROLE_PERMISSIONS` dict
- **Permission Service** (`services.py`): Core logic for permission checking via `has_permission()` function
- **Dependencies** (`dependencies.py`): FastAPI dependency factory `require_permission()` for route protection

### Usage Pattern
Routes use the permission system through FastAPI dependencies:

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

### Security Features
- **Organization Scoping**: All permissions are validated within the context of a specific organization
- **JWT Integration**: Works with Supabase JWT tokens for user authentication
- **Fail-Safe**: Returns HTTP 403 Forbidden when permissions are insufficient
- **Type Safety**: Full type annotations with mypy strict mode compliance

## Key Files and Locations

| File | Purpose | Location |
|------|---------|----------|
| Permission definitions | Enum and role mappings | `src/shared/permissions/models.py:7-93` |
| Permission checking logic | Core validation function | `src/shared/permissions/services.py:6-17` |
| Route protection | FastAPI dependency factory | `src/shared/permissions/dependencies.py:15-62` |

## Usage Examples in Codebase

The permission system is actively used across these domains:
- **Organizations**: Member management routes (`src/domains/organizations/routes.py`)
- **Bank Accounts**: Account management routes (`src/domains/bankaccounts/routes.py`) 
- **External Accounting**: Integration and sync routes (`src/domains/external_accounting/routes.py`)
- **Remittances**: Remittance processing routes (`src/domains/remittances/routes.py`)

Each route that requires authorization uses `require_permission()` with the appropriate permission enum value.