# RemitMatch v03 Architecture Diagrams

## 1. Entity Relationship Diagram - Database Schema

```mermaid
erDiagram
    Profile ||--o{ AuthLink : "has"
    Profile ||--o{ OrganizationMember : "has memberships"
    Profile ||--o{ XeroConnection : "creates"
    Profile ||--o{ XeroSyncLog : "initiates"
    Profile }o--|| Organization : "last accessed"
    
    Organization ||--o{ OrganizationMember : "has members"
    Organization ||--o{ Remittance : "processes"
    Organization ||--o{ Invoice : "manages"
    Organization ||--o{ BankAccount : "owns"
    Organization ||--o{ AuditLog : "tracks"
    Organization ||--|| XeroConnection : "has"
    Organization ||--o{ XeroSyncLog : "logs"
    
    OrganizationMember {
        uuid id PK
        uuid profileId FK
        uuid organizationId FK
        enum role "owner|admin|user|auditor"
        enum status "active|invited|removed"
        datetime joinedAt
    }
    
    Remittance ||--o{ RemittanceLine : "contains"
    Remittance ||--o{ AuditLog : "tracks changes"
    Remittance {
        uuid id PK
        uuid organizationId FK
        string filename
        string filePath
        enum status "Uploaded|Processing|Exported|Reconciled..."
        date paymentDate
        decimal totalAmount
        string reference
        decimal confidenceScore
        json extractedRawJson
    }
    
    RemittanceLine }o--|| Invoice : "AI matched"
    RemittanceLine }o--|| Invoice : "manual override"
    RemittanceLine {
        uuid id PK
        uuid remittanceId FK
        string invoiceNumber
        decimal aiPaidAmount
        decimal manualPaidAmount
        uuid aiInvoiceId FK
        uuid overrideInvoiceId FK
    }
    
    Invoice {
        uuid id PK
        uuid organizationId FK
        string invoiceId "Xero ID"
        string invoiceNumber
        string contactName
        date invoiceDate
        date dueDate
        enum status "DRAFT|SUBMITTED|AUTHORISED|PAID|VOIDED"
        decimal total
        decimal amountDue
        decimal amountPaid
        string currencyCode
    }
    
    BankAccount {
        uuid id PK
        uuid organizationId FK
        string xeroAccountId
        string xeroName
        string xeroCode
        string type "BANK"
        boolean isDefault
        string currencyCode
        boolean enablePaymentsToAccount
    }
    
    XeroConnection {
        uuid id PK
        uuid organizationId FK "unique"
        string xeroTenantId "unique"
        string accessToken
        string refreshToken
        datetime expiresAt
        enum connectionStatus "connected|expired|revoked|error"
        datetime lastSyncAt
        enum syncStatus "pending|syncing|completed|failed"
    }
    
    AuditLog {
        uuid id PK
        uuid remittanceId FK
        uuid userId FK
        uuid organizationId FK
        enum action "created|updated|approved|exported..."
        enum outcome "success|error|rejected|pending"
        datetime timestamp
        string fieldChanged
        string oldValue
        string newValue
        json metadata
    }
```

## 2. Architecture Component Diagram

```mermaid
graph TB
    subgraph "Frontend Application"
        UI[React UI]
    end
    
    subgraph "FastAPI Backend"
        API[FastAPI App]
        
        subgraph "Domains"
            AUTH[Auth Domain<br/>- JWT validation<br/>- Sessions<br/>- Profile management]
            ORG[Organizations Domain<br/>- Multi-tenancy<br/>- Member management<br/>- Role assignment]
            REM[Remittances Domain<br/>- Upload processing<br/>- AI extraction<br/>- Status workflow]
            INV[Invoices Domain<br/>- Invoice sync<br/>- Status tracking<br/>- Currency support]
            BANK[Bank Accounts Domain<br/>- Account management<br/>- Default selection<br/>- Payment config]
            EXT[External Accounting Domain<br/>- Provider abstraction<br/>- Xero integration<br/>- Sync orchestration]
        end
        
        subgraph "Shared Components"
            PERM[Permissions System<br/>- RBAC<br/>- Route protection<br/>- Permission checks]
            EXC[Exception Handling]
            UTILS[Utilities]
        end
        
        subgraph "Core Services"
            DB[Prisma ORM<br/>Database Layer]
            SETTINGS[Settings<br/>Configuration]
        end
    end
    
    subgraph "External Services"
        SUPA[Supabase<br/>- Authentication<br/>- File Storage]
        XERO[Xero API<br/>- Accounting data<br/>- OAuth2]
        OPENAI[OpenAI API<br/>- Document extraction<br/>- AI processing]
        PG[(PostgreSQL<br/>Database)]
    end
    
    UI --> API
    API --> AUTH
    API --> ORG
    API --> REM
    API --> INV
    API --> BANK
    API --> EXT
    
    AUTH --> SUPA
    REM --> OPENAI
    EXT --> XERO
    
    AUTH --> PERM
    ORG --> PERM
    REM --> PERM
    INV --> PERM
    BANK --> PERM
    EXT --> PERM
    
    PERM --> DB
    AUTH --> DB
    ORG --> DB
    REM --> DB
    INV --> DB
    BANK --> DB
    EXT --> DB
    
    DB --> PG
    
    style AUTH fill:#e1f5fe
    style ORG fill:#e8f5e9
    style REM fill:#fff3e0
    style INV fill:#fce4ec
    style BANK fill:#f3e5f5
    style EXT fill:#e8eaf6
    style PERM fill:#ffebee
```

## 3. Remittance Processing Workflow Sequence Diagram

```mermaid
sequenceDiagram
    participant User
    participant API
    participant RemittanceService
    participant FileStorage
    participant OpenAI
    participant InvoiceService
    participant XeroService
    participant Database
    
    User->>API: Upload remittance PDF
    API->>RemittanceService: processUpload(file)
    RemittanceService->>FileStorage: store(file)
    FileStorage-->>RemittanceService: filePath
    
    RemittanceService->>Database: createRemittance(status=Uploaded)
    Database-->>RemittanceService: remittanceId
    
    RemittanceService->>OpenAI: extractData(filePath)
    Note over OpenAI: AI-powered extraction<br/>using Assistant API
    OpenAI-->>RemittanceService: extractedData
    
    RemittanceService->>Database: updateRemittance(status=Processing)
    
    loop For each invoice line
        RemittanceService->>InvoiceService: matchInvoice(invoiceNumber)
        Note over InvoiceService: Three-pass matching:<br/>1. Exact match<br/>2. Relaxed match<br/>3. Numeric match
        InvoiceService->>Database: findInvoice(criteria)
        Database-->>InvoiceService: invoice or null
        InvoiceService-->>RemittanceService: matchResult
        
        RemittanceService->>Database: createRemittanceLine(matchData)
    end
    
    RemittanceService->>Database: updateRemittance(status=Awaiting_Approval)
    
    User->>API: reviewMatches()
    API-->>User: matchResults
    
    opt Manual Override
        User->>API: overrideMatch(lineId, invoiceId)
        API->>RemittanceService: updateMatch()
        RemittanceService->>Database: updateRemittanceLine(overrideInvoiceId)
    end
    
    User->>API: approveRemittance()
    API->>RemittanceService: export(remittanceId)
    
    RemittanceService->>Database: updateRemittance(status=Exporting)
    
    RemittanceService->>XeroService: createBatchPayment(paymentData)
    XeroService->>XeroService: OAuth token refresh
    XeroService-->>RemittanceService: batchId
    
    RemittanceService->>Database: updateRemittance(status=Exported_Unreconciled)
    RemittanceService->>Database: createAuditLog(action=exported)
    
    API-->>User: Export successful
```

## 4. Domain Model Class Diagram

```mermaid
classDiagram
    class Organization {
        +UUID id
        +String name
        +String subscriptionTier
        +DateTime createdAt
        +DateTime updatedAt
        +getMembers()
        +addMember(profile, role)
        +removeMember(profileId)
    }
    
    class Profile {
        +UUID id
        +String email
        +String displayName
        +UUID lastAccessedOrgId
        +DateTime createdAt
        +getMemberships()
        +switchOrganization(orgId)
    }
    
    class OrganizationMember {
        +UUID id
        +UUID profileId
        +UUID organizationId
        +OrganizationRole role
        +MemberStatus status
        +DateTime joinedAt
        +hasPermission(permission)
    }
    
    class Remittance {
        +UUID id
        +String filename
        +RemittanceStatus status
        +Date paymentDate
        +Decimal totalAmount
        +String reference
        +Decimal confidenceScore
        +process()
        +approve()
        +export()
        +reconcile()
    }
    
    class RemittanceLine {
        +UUID id
        +String invoiceNumber
        +Decimal aiPaidAmount
        +Decimal manualPaidAmount
        +UUID aiInvoiceId
        +UUID overrideInvoiceId
        +matchInvoice()
        +overrideMatch(invoiceId)
    }
    
    class Invoice {
        +UUID id
        +String invoiceNumber
        +String contactName
        +Date invoiceDate
        +InvoiceStatus status
        +Decimal total
        +Decimal amountDue
        +String currencyCode
        +syncFromXero()
        +markAsPaid()
    }
    
    class XeroConnection {
        +UUID id
        +String xeroTenantId
        +String accessToken
        +DateTime expiresAt
        +XeroConnectionStatus status
        +XeroSyncStatus syncStatus
        +refreshToken()
        +sync(objectType)
        +disconnect()
    }
    
    class PermissionService {
        +checkPermission(member, permission)
        +requirePermission(permission)
        +getRolePermissions(role)
    }
    
    class SyncOrchestrator {
        +syncInvoices(dataService, orgId, options)
        +syncAccounts(dataService, orgId)
        +handleSyncError(error)
    }
    
    Organization "1" --> "*" OrganizationMember
    Profile "1" --> "*" OrganizationMember
    Organization "1" --> "*" Remittance
    Organization "1" --> "*" Invoice
    Organization "1" --> "0..1" XeroConnection
    Remittance "1" --> "*" RemittanceLine
    RemittanceLine "*" --> "0..1" Invoice : AI matched
    RemittanceLine "*" --> "0..1" Invoice : manual override
    OrganizationMember ..> PermissionService : uses
    XeroConnection ..> SyncOrchestrator : uses
```

## 5. Permission System Flow Diagram

```mermaid
flowchart TD
    A[API Request] --> B{Authenticated?}
    B -->|No| C[401 Unauthorized]
    B -->|Yes| D[Extract JWT Token]
    
    D --> E[Get User Profile]
    E --> F[Get Organization Membership]
    
    F --> G{Member exists?}
    G -->|No| H[403 Forbidden]
    G -->|Yes| I[Get Member Role]
    
    I --> J[Map Role to Permissions]
    
    J --> K{Has required<br/>permission?}
    K -->|No| L[403 Forbidden]
    K -->|Yes| M[Execute Route Handler]
    
    subgraph "Role Permission Mapping"
        OWNER[Owner Role<br/>- All permissions]
        ADMIN[Admin Role<br/>- Most permissions<br/>- No billing]
        USER[User Role<br/>- Basic view permissions]
        AUDITOR[Auditor Role<br/>- Read-only access]
    end
    
    subgraph "Available Permissions"
        P1[VIEW_MEMBERS]
        P2[MANAGE_MEMBERS]
        P3[VIEW_BANK_ACCOUNTS]
        P4[MANAGE_BANK_ACCOUNTS]
        P5[VIEW_INVOICES]
        P6[SYNC_INVOICES]
        P7[CREATE_PAYMENTS]
        P8[MANAGE_BILLING]
    end
```

## 6. External Accounting Integration Architecture

```mermaid
graph TB
    subgraph "API Layer"
        ROUTE[/external-accounting/*<br/>API Routes]
    end
    
    subgraph "Provider Abstraction Layer"
        FACTORY[IntegrationFactory<br/>Provider Resolution]
        BASE[BaseIntegrationDataService<br/>Abstract Interface]
        ORCH[SyncOrchestrator<br/>Generic Sync Logic]
    end
    
    subgraph "Provider Implementations"
        XERO_IMPL[XeroDataService<br/>Xero Implementation]
        FUTURE1[FutureProvider1<br/>QuickBooks/MYOB/etc]
        FUTURE2[FutureProvider2<br/>Other Providers]
    end
    
    subgraph "Provider Services"
        XERO_API[Xero API<br/>OAuth2 + REST]
        OTHER_API[Other APIs<br/>Future Providers]
    end
    
    subgraph "Database"
        CONN[(Provider Connections<br/>XeroConnection table)]
        DATA[(Synced Data<br/>Invoices, Accounts)]
        LOGS[(Sync Logs<br/>XeroSyncLog table)]
    end
    
    ROUTE --> FACTORY
    FACTORY --> BASE
    FACTORY --> CONN
    
    BASE <-.-> XERO_IMPL
    BASE <-.-> FUTURE1
    BASE <-.-> FUTURE2
    
    XERO_IMPL --> XERO_API
    FUTURE1 --> OTHER_API
    FUTURE2 --> OTHER_API
    
    ORCH --> BASE
    ORCH --> DATA
    ORCH --> LOGS
    
    style BASE fill:#e8eaf6
    style FACTORY fill:#e8eaf6
    style ORCH fill:#e8eaf6
    style XERO_IMPL fill:#c5e1a5
    style FUTURE1 fill:#ffccbc,stroke-dasharray: 5 5
    style FUTURE2 fill:#ffccbc,stroke-dasharray: 5 5
```

## 7. Invoice Matching Algorithm Flowchart

```mermaid
flowchart TD
    A[Start: Invoice Number<br/>from Remittance Line] --> B[Normalize Input<br/>- Trim whitespace<br/>- Convert to uppercase]
    
    B --> C{Exact Match?<br/>Case-insensitive}
    C -->|Yes| D[Return Match<br/>Confidence: 100%]
    C -->|No| E[Relaxed Match<br/>Remove special chars]
    
    E --> F{Relaxed Match<br/>Found?}
    F -->|Yes| G[Return Match<br/>Confidence: 85%]
    F -->|No| H[Extract Numbers Only]
    
    H --> I{Numeric Match<br/>Found?}
    I -->|Yes| J[Return Match<br/>Confidence: 70%]
    I -->|No| K[No Match Found]
    
    K --> L{Manual Override<br/>Available?}
    L -->|Yes| M[Use Override Invoice]
    L -->|No| N[Mark as Unmatched]
    
    subgraph "Matching Examples"
        EX1[Input: "INV-001"<br/>Exact: "INV-001" ✓]
        EX2[Input: "INV 001"<br/>Relaxed: "INV001" ✓]
        EX3[Input: "Invoice #001"<br/>Numeric: "001" ✓]
    end
```

## 8. Audit Trail Activity Diagram

```mermaid
flowchart LR
    subgraph "Remittance Lifecycle"
        A[Upload File] --> B[Create Audit Log<br/>action: created]
        B --> C[Process File]
        C --> D[Create Audit Log<br/>action: updated]
        D --> E[Manual Override]
        E --> F[Create Audit Log<br/>action: manual_override]
        F --> G[Approve]
        G --> H[Create Audit Log<br/>action: approved]
        H --> I[Export to Xero]
        I --> J[Create Audit Log<br/>action: exported]
        J --> K[Reconcile]
        K --> L[Create Audit Log<br/>action: reconciled]
    end
    
    subgraph "Audit Log Structure"
        LOG[AuditLog Entry<br/>- remittanceId<br/>- userId<br/>- organizationId<br/>- action<br/>- outcome<br/>- timestamp<br/>- fieldChanged<br/>- oldValue<br/>- newValue<br/>- metadata]
    end
    
    B --> LOG
    D --> LOG
    F --> LOG
    H --> LOG
    J --> LOG
    L --> LOG
```

These diagrams provide a comprehensive visual representation of the RemitMatch v03 architecture, including:

1. **Entity Relationship Diagram**: Shows the complete database schema with all relationships
2. **Architecture Component Diagram**: Illustrates the system's modular architecture and external dependencies
3. **Remittance Processing Workflow**: Details the end-to-end process from upload to reconciliation
4. **Domain Model Class Diagram**: Shows the object-oriented design of key business entities
5. **Permission System Flow**: Explains the RBAC authorization process
6. **External Accounting Integration**: Demonstrates the provider-agnostic design pattern
7. **Invoice Matching Algorithm**: Visualizes the three-pass matching logic
8. **Audit Trail Activity**: Shows how the system tracks all business actions

All diagrams follow Mermaid syntax and can be rendered using any Mermaid-compatible viewer.