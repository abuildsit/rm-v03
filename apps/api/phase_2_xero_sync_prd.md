### Phase 2 PRD – Xero Data Synchronisation (Invoices & Accounts)

#### Context

- Builds on Phase 1 (Auth Flow) but focuses on **fetching and syncing invoices and accounts**.
- Uses **class-based structure** (idiomatic FastAPI, modular), but keeps it simple.
- File structure (code):
  ```
  src/domains/external_accounting/
      base/              # Shared base classes (IntegrationFactory, BaseClient, etc.)
      xero/
          data/
              accounting_client.py   # Low-level Xero API calls (invoices/accounts)
              sync_service.py        # Orchestration: fetch + upsert to DB
              routes.py              # Endpoints: /external-accounting/invoices, /external-accounting/accounts
  ```

#### Endpoints

- ``

  - Sync invoices from Xero to local DB.
  - Query params: `incremental`, `invoice_types[]`, `months_back`.
  - Returns summary (success, count, duration). Does **not** return invoices.

- ``

  - Sync chart of accounts (bank + general accounts) to local DB.
  - Query params: `account_types[]` (optional filter).
  - Returns summary (success, count, duration).

Both use `IntegrationFactory` to resolve correct provider client (currently only Xero).

#### Key Components

1. ``** (XeroAccountingClient)**

   - Encapsulates **all raw API calls to Xero** (flexible filtering, pagination, retries).
   - Examples:
     ```pseudocode
     class XeroAccountingClient:
         def get_invoices(org_id, type=None, status=None, date_from=None, date_to=None, modified_since=None, page=1) -> dict
         def get_accounts(org_id, type=None) -> dict
     ```
   - Handles:
     - Token via `XeroAuthManager`
     - Xero headers (tenant ID)
     - Retries & rate limits

2. ``** (XeroSyncService)**

   - Uses `XeroAccountingClient` to fetch.
   - Handles upserts into DB.
   - Two-phase invoice sync (12 months + all AUTHORISED).
   - Logs results (success, errors, counts).
   - Example methods:
     ```pseudocode
     class XeroSyncService:
         def sync_invoices(org_id, incremental, invoice_types, months_back) -> SyncResult
         def sync_accounts(org_id, account_types) -> SyncResult
     ```

3. ``

   - Resolves which client/service to use based on organisation’s integration (currently Xero).
   - Example:
     ```pseudocode
     class IntegrationFactory:
         def get_sync_service(org_id) -> BaseSyncService
     ```

#### Flow Example (Invoice Sync)

1. `POST /integrations/invoices/sync?org_id=123&incremental=true`
2. Route validates user/org via `OrganizationService`.
3. Uses `IntegrationFactory` to get `XeroSyncService`.
4. `XeroSyncService.sync_invoices()`:
   - Calls `XeroAccountingClient.get_invoices()` (with filters/pagination).
   - Deduplicates invoices.
   - Upserts to `invoices` table.
   - Logs operation (counts, errors).
5. Returns `SyncResult` (JSON):
   ```json
   {
     "object_type": "invoices",
     "success": true,
     "count": 250,
     "duration_seconds": 42.8,
     "last_modified": "2025-07-22T14:30:00Z"
   }
   ```

#### Notes

- All **auth/token logic** is handled by Phase 1 components (`XeroAuthManager`).
- Background sync **can be deferred** (not blocking endpoints).
- Supports **multi-tenant (multiple Xero orgs)** per customer.
- Tokens **must be encrypted** at rest (handled in Phase 1).

Would you like me to now add:

1. **Pseudocode for **`` (with filtering/pagination)?
2. **Pseudocode for **`` showing how endpoints link to services?

