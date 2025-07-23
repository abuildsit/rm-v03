# RemitMatch - Remittance Processing Feature PRD

## Table of Contents
1. [Executive Summary](#executive-summary)
2. [Problem Statement](#problem-statement)
3. [Solution Overview](#solution-overview)
4. [Technical Architecture](#technical-architecture)
5. [Feature Specifications](#feature-specifications)
6. [API Specifications](#api-specifications)
7. [Data Models](#data-models)
8. [User Workflows](#user-workflows)
9. [Security & Permissions](#security-permissions)
10. [Performance Requirements](#performance-requirements)
11. [Success Metrics](#success-metrics)
12. [Implementation Phases](#implementation-phases)
13. [Risks & Mitigations](#risks-mitigations)

## Executive Summary

RemitMatch is a web application that streamlines the reconciliation of remittance advice documents with invoice data from accounting software. This PRD outlines the core remittance processing feature that enables users to upload remittance PDFs, automatically extract payment information using AI, and intelligently match payments against existing invoices.

### Key Capabilities
- **AI-Powered Extraction**: Automated extraction of payment data from PDF remittance documents using OpenAI
- **Intelligent Matching**: Three-pass progressive matching algorithm (exact → relaxed → numeric)
- **Manual Override**: User ability to correct AI matches with audit trail
- **Multi-tenant**: Organization-based data isolation with role-based permissions
- **High Performance**: Optimized for processing thousands of invoices with sub-second matching

### Target Users
- **Accounts Receivable Teams**: Primary users processing remittances daily
- **Finance Managers**: Oversight and analytics on payment reconciliation
- **Auditors**: Read-only access for compliance and verification

## Problem Statement

### Current Pain Points
1. **Manual Data Entry**: Staff spend hours manually entering payment details from PDF remittances
2. **Error-Prone Process**: Manual entry leads to mistakes in payment allocation
3. **Slow Reconciliation**: Processing remittances takes days instead of minutes
4. **Inconsistent Formats**: Remittance documents vary widely in format and structure
5. **Poor Visibility**: Limited tracking of payment status and reconciliation metrics

### Business Impact
- **Labor Cost**: 2-4 hours per day per AR staff member on manual reconciliation
- **Cash Flow**: Delayed payment recognition impacts working capital
- **Customer Relations**: Incorrect payment allocation leads to false dunning notices
- **Audit Risk**: Manual processes lack proper audit trails

## Solution Overview

### Core Components

#### 1. AI Document Extraction
- Upload remittance PDFs through web interface
- OpenAI Assistant API extracts structured payment data
- Validation ensures data quality before processing
- Confidence scoring for extraction accuracy

#### 2. Intelligent Invoice Matching
- **Pass 1 - Exact Match**: Case-insensitive, whitespace-normalized matching
- **Pass 2 - Relaxed Match**: Remove special characters and punctuation
- **Pass 3 - Numeric Match**: Extract and match numeric components only
- O(1) performance using lookup tables
- Confidence scoring for each match type

#### 3. Manual Review & Override
- Visual interface showing AI matches with confidence scores
- Ability to override incorrect matches
- Search functionality to find correct invoices
- Audit trail of all manual interventions

#### 4. Integration & Automation
- Seamless integration with Xero (and future accounting systems)
- Automatic status updates for matched invoices
- Background processing for large documents
- Real-time progress tracking

## Technical Architecture

### System Components

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Web Frontend  │────▶│  FastAPI Backend │────▶│   PostgreSQL    │
│   (React/Next)  │     │   (Python 3.11)  │     │   (via Prisma)  │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                               │
                               ├──────────────────┐
                               ▼                  ▼
                        ┌──────────────┐   ┌──────────────┐
                        │  OpenAI API  │   │  File Storage│
                        │  (Assistant) │   │  (S3/Local)  │
                        └──────────────┘   └──────────────┘
```

### File Structure

```
src/
├── core/
│   ├── database.py             # Prisma connection
│   ├── settings.py             # Configuration + OpenAI/storage settings
│   └── storage.py              # File storage abstraction (S3/local)
├── shared/
│   ├── ai/
│   │   ├── client.py           # OpenAI client wrapper
│   │   ├── config.py           # AI configuration
│   │   └── exceptions.py       # AI-related exceptions
│   └── permissions/
│       └── models.py           # Extended with remittance permissions
└── domains/
    └── remittances/
        ├── models.py           # Data models
        ├── routes.py           # API endpoints
        ├── service.py          # Orchestration layer
        ├── types.py            # Enums and types
        ├── exceptions.py       # Domain exceptions
        ├── ai_extraction/
        │   ├── service.py      # AI extraction service
        │   ├── prompts.py      # Remittance-specific prompts
        │   └── validation.py   # Response validation
        └── matching/
            ├── service.py      # Matching engine
            ├── strategies.py   # Normalization strategies
            └── confidence.py   # Confidence calculation
```

## Feature Specifications

### 1. Document Upload & Processing

#### Requirements
- **File Types**: PDF support (initial), expandable to other formats
- **File Size**: Maximum 10MB per file
- **Validation**: File type, size, and virus scanning
- **Storage**: Secure storage with encryption at rest
- **Processing**: Asynchronous with progress tracking

#### User Interface
- Drag-and-drop upload area
- File preview before processing
- Upload progress indicator
- Processing status display
- Error messaging for invalid files

### 2. AI Extraction

#### OpenAI Integration
- **Model**: GPT-4 via Assistant API
- **Prompts**: Specialized for remittance extraction
- **Retry Logic**: Exponential backoff with 3 attempts
- **Timeout**: 300 seconds maximum processing time
- **Rate Limiting**: Respect OpenAI rate limits

#### Extracted Data
```json
{
  "Date": "2024-01-15",
  "TotalAmount": 15000.00,
  "PaymentReference": "PAYMENT-2024-001",
  "Payments": [
    {
      "InvoiceNo": "INV-2024-001",
      "PaidAmount": 5000.00
    },
    {
      "InvoiceNo": "INV-2024-002", 
      "PaidAmount": 10000.00
    }
  ],
  "confidence": 0.92
}
```

#### Validation Rules
- Total amount must equal sum of payment amounts
- Invoice numbers must be non-empty
- Payment amounts must be positive
- Confidence score between 0 and 1

### 3. Invoice Matching

#### Three-Pass Strategy

**Pass 1 - Exact Match**
- Trim whitespace
- Convert to uppercase
- Match against invoice database
- Confidence: 0.95

**Pass 2 - Relaxed Match**
- Remove all non-alphanumeric characters
- Example: "INV-2024-001" → "INV2024001"
- Confidence: 0.85

**Pass 3 - Numeric Match**
- Extract numeric components only
- Example: "INV-2024-001" → "2024001"
- Confidence: 0.70

#### Performance Optimization
- Build lookup tables for O(1) matching
- Early termination when all lines matched
- Batch database operations
- Caching for repeated operations

### 4. Manual Review Interface

#### Match Review Screen
- Side-by-side display: Extracted data vs Matched invoices
- Confidence indicators (color-coded)
- Unmatched items highlighted
- Quick actions: Approve, Override, Skip

#### Override Functionality
- Search invoices by number, customer, amount
- Autocomplete suggestions
- Reason for override (optional)
- Audit trail maintenance

### 5. Status Management

#### Remittance Statuses
- **Uploaded**: File received, awaiting processing
- **Processing**: AI extraction in progress
- **Extracted**: Data extracted, awaiting matching
- **Matched**: Automatic matching complete
- **Partially_Matched**: Some lines matched
- **Completed**: All processing finished
- **Failed**: Processing error occurred

#### Status Transitions
```
Uploaded → Processing → Extracted → Matched/Partially_Matched → Completed
     ↓           ↓            ↓              ↓
   Failed     Failed       Failed         Failed
```

## API Specifications

### Base URL
`/api/v1/remittances`

### Endpoints

#### 1. Upload Remittance
```http
POST /organizations/{org_id}/remittances
Content-Type: multipart/form-data
Authorization: Bearer {token}

Body:
- file: binary (PDF file)
- metadata: { "description": "optional description" }

Response 201:
{
  "id": "uuid",
  "filename": "remittance_2024_01.pdf",
  "status": "uploaded",
  "created_at": "2024-01-15T10:00:00Z"
}
```

#### 2. List Remittances
```http
GET /organizations/{org_id}/remittances
Authorization: Bearer {token}

Query Parameters:
- status: string (comma-separated)
- date_from: date
- date_to: date
- limit: integer (default: 20, max: 100)
- offset: integer

Response 200:
{
  "data": [
    {
      "id": "uuid",
      "filename": "remittance_2024_01.pdf",
      "upload_date": "2024-01-15T10:00:00Z",
      "status": "completed",
      "total_amount": 15000.00,
      "lines_count": 10,
      "matched_count": 8,
      "match_percentage": 80.0
    }
  ],
  "total": 150,
  "limit": 20,
  "offset": 0
}
```

#### 3. Get Remittance Details
```http
GET /organizations/{org_id}/remittances/{remittance_id}
Authorization: Bearer {token}

Response 200:
{
  "id": "uuid",
  "filename": "remittance_2024_01.pdf",
  "upload_date": "2024-01-15T10:00:00Z",
  "status": "completed",
  "total_amount": 15000.00,
  "payment_date": "2024-01-15",
  "payment_reference": "PAYMENT-2024-001",
  "confidence_score": 0.92,
  "lines": [
    {
      "id": "uuid",
      "line_number": 1,
      "invoice_number": "INV-2024-001",
      "ai_paid_amount": 5000.00,
      "matched_invoice": {
        "id": "uuid",
        "number": "INV-2024-001",
        "customer_name": "ABC Corp",
        "total": 5000.00
      },
      "match_confidence": 0.95,
      "match_type": "exact"
    }
  ],
  "summary": {
    "total_lines": 10,
    "matched_count": 8,
    "unmatched_count": 2,
    "match_percentage": 80.0,
    "exact_matches": 5,
    "relaxed_matches": 2,
    "numeric_matches": 1
  }
}
```

#### 4. Trigger Matching
```http
POST /organizations/{org_id}/remittances/{remittance_id}/match
Authorization: Bearer {token}

Body:
{
  "force_rematch": true
}

Response 202:
{
  "status": "processing",
  "message": "Matching initiated"
}
```

#### 5. Override Match
```http
PUT /organizations/{org_id}/remittances/{remittance_id}/lines/{line_id}
Authorization: Bearer {token}

Body:
{
  "override_invoice_id": "uuid",
  "notes": "Corrected invoice number typo"
}

Response 200:
{
  "id": "uuid",
  "invoice_number": "INV-2024-001",
  "override_invoice_id": "uuid",
  "notes": "Corrected invoice number typo",
  "updated_at": "2024-01-15T11:00:00Z"
}
```

#### 6. Get Processing Status
```http
GET /organizations/{org_id}/remittances/{remittance_id}/status
Authorization: Bearer {token}

Response 200:
{
  "status": "processing",
  "progress": 65,
  "current_step": "matching_invoices",
  "estimated_completion": "2024-01-15T10:05:00Z"
}
```

## Data Models

### Pydantic Models

```python
from pydantic import BaseModel, Field
from decimal import Decimal
from datetime import datetime, date
from typing import Optional, List
from uuid import UUID
from enum import Enum

class RemittanceStatus(str, Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    EXTRACTED = "extracted"
    MATCHED = "matched"
    PARTIALLY_MATCHED = "partially_matched"
    COMPLETED = "completed"
    FAILED = "failed"

class MatchingPassType(str, Enum):
    EXACT = "exact"
    RELAXED = "relaxed"
    NUMERIC = "numeric"

class RemittanceCreate(BaseModel):
    filename: str
    file_size: int
    description: Optional[str] = None

class RemittanceLine(BaseModel):
    id: UUID
    remittance_id: UUID
    line_number: int
    invoice_number: str
    ai_paid_amount: Decimal
    ai_invoice_id: Optional[UUID] = None
    override_invoice_id: Optional[UUID] = None
    match_confidence: Optional[Decimal] = Field(None, ge=0, le=1)
    match_type: Optional[MatchingPassType] = None
    notes: Optional[str] = None

class Remittance(BaseModel):
    id: UUID
    organization_id: UUID
    filename: str
    file_url: Optional[str] = None
    upload_date: datetime
    status: RemittanceStatus
    total_amount: Optional[Decimal] = None
    payment_date: Optional[date] = None
    payment_reference: Optional[str] = None
    confidence_score: Optional[Decimal] = Field(None, ge=0, le=1)
    lines_count: int = 0
    matched_lines_count: int = 0
    created_by: UUID

class MatchingSummary(BaseModel):
    total_lines: int
    matched_count: int
    unmatched_count: int
    match_percentage: Decimal
    exact_matches: int = 0
    relaxed_matches: int = 0
    numeric_matches: int = 0
    processing_time_ms: int
```

## User Workflows

### Workflow 1: Upload and Process Remittance

1. **User Action**: Navigate to Remittances section
2. **System**: Display remittance list with upload button
3. **User Action**: Click "Upload Remittance" button
4. **System**: Show upload modal with drag-drop area
5. **User Action**: Drag PDF file or click to browse
6. **System**: Validate file type and size
7. **User Action**: Click "Process" button
8. **System**: 
   - Upload file to storage
   - Create remittance record
   - Trigger AI extraction
   - Show processing status
9. **System**: Extract payment data using AI
10. **System**: Run automatic matching
11. **System**: Display results summary
12. **User Action**: Review matches

### Workflow 2: Review and Override Matches

1. **User Action**: Click on processed remittance
2. **System**: Display remittance details with line items
3. **User Action**: Identify incorrect match (low confidence)
4. **System**: Highlight confidence score
5. **User Action**: Click "Override" on line item
6. **System**: Show invoice search interface
7. **User Action**: Search for correct invoice
8. **System**: Display search results
9. **User Action**: Select correct invoice
10. **System**: Update match and recalculate summary
11. **User Action**: Add optional notes
12. **System**: Save override with audit trail

### Workflow 3: Bulk Processing

1. **User Action**: Select multiple uploaded remittances
2. **System**: Enable bulk actions menu
3. **User Action**: Click "Process Selected"
4. **System**: Queue all remittances for processing
5. **System**: Show progress for each file
6. **User Action**: Continue other work
7. **System**: Send notification when complete
8. **User Action**: Review bulk results summary

## Security & Permissions

### Role-Based Permissions

```python
class Permission(str, Enum):
    # Remittance-specific permissions
    VIEW_REMITTANCES = "view_remittances"
    PROCESS_REMITTANCES = "process_remittances"
    MANAGE_REMITTANCES = "manage_remittances"
    MANAGE_REMITTANCE_MATCHES = "manage_remittance_matches"
    VIEW_ANALYTICS = "view_analytics"

# Role mappings
ROLE_PERMISSIONS = {
    OrganizationRole.OWNER: {
        Permission.VIEW_REMITTANCES,
        Permission.PROCESS_REMITTANCES,
        Permission.MANAGE_REMITTANCES,
        Permission.MANAGE_REMITTANCE_MATCHES,
        Permission.VIEW_ANALYTICS,
    },
    OrganizationRole.ADMIN: {
        Permission.VIEW_REMITTANCES,
        Permission.PROCESS_REMITTANCES,
        Permission.MANAGE_REMITTANCE_MATCHES,
        Permission.VIEW_ANALYTICS,
    },
    OrganizationRole.USER: {
        Permission.VIEW_REMITTANCES,
        Permission.PROCESS_REMITTANCES,
    },
    OrganizationRole.AUDITOR: {
        Permission.VIEW_REMITTANCES,
        Permission.VIEW_ANALYTICS,
    }
}
```

### Security Requirements

1. **File Upload Security**
   - Virus scanning on upload
   - File type validation (PDF only initially)
   - Size limits enforcement
   - Secure storage with encryption

2. **Data Isolation**
   - Strict organization-based data separation
   - No cross-organization data access
   - Audit logs for all data access

3. **API Security**
   - JWT authentication required
   - Permission checks on all endpoints
   - Rate limiting per organization
   - Input validation and sanitization

4. **Sensitive Data**
   - No storage of sensitive financial data in logs
   - PII redaction in error messages
   - Secure deletion of processed files

## Performance Requirements

### Response Time SLAs

| Operation | Target | Maximum |
|-----------|--------|---------|
| File Upload (10MB) | < 2s | 5s |
| AI Extraction | < 30s | 60s |
| Invoice Matching (1000 invoices) | < 100ms | 500ms |
| API Response (list) | < 200ms | 1s |
| API Response (detail) | < 100ms | 500ms |

### Scalability Requirements

- Support 100 concurrent users per organization
- Process 1000 remittances per day per organization
- Match against 10,000 invoices per organization
- Store 1 year of historical data

### Optimization Strategies

1. **Caching**
   - Invoice data cached for matching
   - Recent remittances cached
   - User permissions cached

2. **Database**
   - Indexed on organization_id, status, dates
   - Partitioning for large organizations
   - Read replicas for analytics

3. **Background Processing**
   - Queue-based processing for AI extraction
   - Batch matching operations
   - Async file uploads

## Success Metrics

### Key Performance Indicators

1. **Efficiency Metrics**
   - Time saved per remittance: Target 90% reduction
   - Processing time: < 2 minutes end-to-end
   - Matching accuracy: > 85% automatic matches

2. **Quality Metrics**
   - AI extraction accuracy: > 95%
   - False positive rate: < 5%
   - Manual override rate: < 15%

3. **Usage Metrics**
   - Daily active users
   - Remittances processed per day
   - Average remittance size
   - Feature adoption rate

4. **Business Metrics**
   - Days Sales Outstanding (DSO) reduction
   - AR productivity improvement
   - Error rate reduction
   - Customer satisfaction scores

### Measurement Methods

- Application analytics (Mixpanel/Amplitude)
- Database metrics and queries
- User surveys and feedback
- A/B testing for UI improvements

## Implementation Phases

### Phase 1: MVP (Weeks 1-6)
- Basic file upload and storage
- OpenAI integration for extraction
- Simple exact matching
- Manual override capability
- Core API endpoints

### Phase 2: Enhanced Matching (Weeks 7-10)
- Three-pass matching algorithm
- Confidence scoring
- Bulk processing
- Performance optimization
- Enhanced UI for review

### Phase 3: Analytics & Automation (Weeks 11-14)
- Analytics dashboard
- Automated workflows
- Email notifications
- Batch operations
- API webhooks

### Phase 4: Advanced Features (Weeks 15-18)
- Machine learning improvements
- Custom matching rules
- Multi-format support (CSV, Excel)
- Advanced reporting
- Integration marketplace

## Risks & Mitigations

### Technical Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| OpenAI API downtime | High | Implement fallback providers, queue for retry |
| Poor extraction accuracy | High | Human review queue, continuous prompt improvement |
| Performance degradation | Medium | Caching, database optimization, horizontal scaling |
| Storage costs | Medium | Implement retention policies, compression |

### Business Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Low user adoption | High | Comprehensive training, gradual rollout |
| Compliance issues | High | Audit trails, data retention policies |
| Integration complexity | Medium | Phased integration approach |
| Change resistance | Medium | Show ROI metrics, success stories |

### Security Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Data breach | Critical | Encryption, access controls, security audits |
| Unauthorized access | High | Strong authentication, permission system |
| Data loss | High | Regular backups, disaster recovery |
| Compliance violations | High | Regular audits, data governance |

## Conclusion

The RemitMatch remittance processing feature represents a significant advancement in accounts receivable automation. By combining AI-powered extraction with intelligent matching algorithms, we can reduce manual effort by 90% while improving accuracy and providing better visibility into payment processing.

Success depends on:
- Robust technical implementation following best practices
- Intuitive user interface that reduces friction
- Comprehensive testing and quality assurance
- Gradual rollout with user feedback incorporation
- Continuous improvement based on metrics

This PRD provides the foundation for building a feature that will transform how organizations process remittances, saving time, reducing errors, and improving cash flow management.