# Invoice Matching Workflow Integration Guide

## Overview

This guide provides comprehensive instructions for integrating RemitMatch's invoice matching workflow into your applications. The system can be adapted for various document-to-record matching scenarios beyond invoice reconciliation.

## Prerequisites

### Technical Requirements
- Python 3.8+
- Async/await support
- Database system (PostgreSQL, MySQL, SQLite, etc.)
- ORM or database client library

### Dependencies
```bash
pip install pydantic asyncio uuid decimal
# Plus your database client (e.g., asyncpg, aiomysql, etc.)
```

### Data Requirements
- Payment/transaction records with reference numbers
- Invoice/record database with searchable identifiers
- Normalized data access layer

## Architecture Overview

```
Payment Data → Normalization Engine → Matching Algorithm → Result Processing
     ↓              ↓                      ↓                    ↓
   Extract       3-Pass Strategy      O(1) Lookups         Status Updates
   Numbers       (Exact→Relaxed→      Dictionary-based     Database Changes
                    Numeric)          Performance          Audit Logging
```

## Step-by-Step Integration

### 1. Data Model Setup

Define your data models for matching:

```python
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from uuid import UUID
from decimal import Decimal
from enum import Enum

class MatchingPassType(str, Enum):
    EXACT = "exact"
    RELAXED = "relaxed"  
    NUMERIC = "numeric"

class PaymentLine(BaseModel):
    """Individual payment record to be matched"""
    id: UUID
    reference_number: str           # The number to match against
    amount: Decimal
    description: Optional[str] = None
    matched_record_id: Optional[UUID] = None

class InvoiceRecord(BaseModel):
    """Record to match against (invoice, order, etc.)"""
    id: UUID
    reference_number: str           # The searchable identifier
    amount: Decimal
    status: str
    organization_id: UUID

class MatchResult(BaseModel):
    """Result of matching a single payment line"""
    payment_id: UUID
    payment_reference: str
    matched_record_id: Optional[UUID] = None
    matched_reference: Optional[str] = None
    match_type: Optional[MatchingPassType] = None
    confidence: Decimal = Field(default=Decimal('0'), ge=0, le=1)

class MatchingSummary(BaseModel):
    """Overall matching statistics"""
    total_payments: int
    matched_count: int
    unmatched_count: int
    match_percentage: Decimal
    all_matched: bool
    
    # Pass-specific counts
    exact_matches: int = 0
    relaxed_matches: int = 0
    numeric_matches: int = 0
    
    processing_time_ms: int = 0
```

### 2. Core Matching Service

Implement the main matching service:

```python
import asyncio
import logging
from typing import Dict, List, Tuple, Callable

class DocumentMatchingService:
    """
    Generic document matching service using three-pass strategy.
    
    Adaptable for various matching scenarios:
    - Invoice matching
    - Order reconciliation  
    - Payment processing
    - Document correlation
    """
    
    def __init__(self, database_client):
        self.db = database_client
        self.logger = logging.getLogger(__name__)
        
        # Configure matching parameters
        self.batch_size = 1000
        self.max_cache_size = 10000
    
    async def match_payments_to_records(
        self,
        payments: List[PaymentLine],
        records: List[InvoiceRecord],
        organization_id: UUID
    ) -> Dict[str, Any]:
        """
        Main matching method implementing three-pass strategy.
        
        Args:
            payments: Payment lines to match
            records: Available records for matching
            organization_id: Organization context
            
        Returns:
            Complete matching result with statistics
        """
        start_time = asyncio.get_event_loop().time()
        
        if not payments:
            return self._create_empty_result()
        
        if not records:
            return self._create_no_records_result(payments)
        
        self.logger.info(f"Matching {len(payments)} payments against {len(records)} records")
        
        # Execute three-pass matching
        all_matches, unmatched = await self._execute_matching_passes(payments, records)
        
        # Calculate metrics
        processing_time = int((asyncio.get_event_loop().time() - start_time) * 1000)
        
        # Compile result
        return self._compile_results(all_matches, unmatched, payments, processing_time)
    
    async def _execute_matching_passes(
        self,
        payments: List[PaymentLine],
        records: List[InvoiceRecord]
    ) -> Tuple[List[MatchResult], List[PaymentLine]]:
        """Execute the three-pass matching strategy"""
        
        all_matches = []
        unmatched_payments = payments.copy()
        
        # Define normalization strategies
        normalization_passes = [
            (self._exact_normalize, MatchingPassType.EXACT),
            (self._relaxed_normalize, MatchingPassType.RELAXED),
            (self._numeric_normalize, MatchingPassType.NUMERIC)
        ]
        
        for normalizer_func, pass_type in normalization_passes:
            if not unmatched_payments:
                break  # All payments matched
            
            self.logger.debug(f"Starting {pass_type} pass with {len(unmatched_payments)} unmatched")
            
            # Build lookup for this normalization
            record_lookup = self._build_record_lookup(records, normalizer_func)
            
            # Match payments using current strategy
            matches, still_unmatched = self._match_with_lookup(
                unmatched_payments, record_lookup, normalizer_func, pass_type
            )
            
            all_matches.extend(matches)
            unmatched_payments = still_unmatched
            
            self.logger.debug(f"{pass_type} pass matched {len(matches)} payments")
        
        return all_matches, unmatched_payments
    
    def _build_record_lookup(
        self,
        records: List[InvoiceRecord],
        normalizer_func: Callable[[str], str]
    ) -> Dict[str, InvoiceRecord]:
        """Build O(1) lookup dictionary for records"""
        lookup = {}
        
        for record in records:
            if not record.reference_number:
                continue
            
            normalized = normalizer_func(record.reference_number)
            if normalized and normalized not in lookup:
                # First match wins
                lookup[normalized] = record
        
        return lookup
    
    def _match_with_lookup(
        self,
        payments: List[PaymentLine],
        record_lookup: Dict[str, InvoiceRecord],
        normalizer_func: Callable[[str], str],
        pass_type: MatchingPassType
    ) -> Tuple[List[MatchResult], List[PaymentLine]]:
        """Match payments against record lookup"""
        matches = []
        unmatched = []
        
        for payment in payments:
            if not payment.reference_number:
                unmatched.append(payment)
                continue
            
            normalized_ref = normalizer_func(payment.reference_number)
            
            if normalized_ref in record_lookup:
                matched_record = record_lookup[normalized_ref]
                
                match = MatchResult(
                    payment_id=payment.id,
                    payment_reference=payment.reference_number,
                    matched_record_id=matched_record.id,
                    matched_reference=matched_record.reference_number,
                    match_type=pass_type,
                    confidence=self._calculate_confidence(pass_type, payment, matched_record)
                )
                
                matches.append(match)
            else:
                unmatched.append(payment)
        
        return matches, unmatched
    
    # Normalization Functions
    
    def _exact_normalize(self, reference: str) -> str:
        """Exact normalization with case and whitespace handling"""
        return reference.strip().upper() if reference else ""
    
    def _relaxed_normalize(self, reference: str) -> str:
        """Remove all non-alphanumeric characters"""
        if not reference:
            return ""
        normalized = self._exact_normalize(reference)
        return ''.join(c for c in normalized if c.isalnum())
    
    def _numeric_normalize(self, reference: str) -> str:
        """Extract digits only"""
        return ''.join(c for c in reference if c.isdigit()) if reference else ""
    
    def _calculate_confidence(
        self,
        pass_type: MatchingPassType,
        payment: PaymentLine,
        record: InvoiceRecord
    ) -> Decimal:
        """Calculate match confidence score"""
        base_scores = {
            MatchingPassType.EXACT: Decimal('0.95'),
            MatchingPassType.RELAXED: Decimal('0.85'),
            MatchingPassType.NUMERIC: Decimal('0.70')
        }
        
        confidence = base_scores.get(pass_type, Decimal('0.5'))
        
        # Adjust for amount similarity (optional enhancement)
        if payment.amount == record.amount:
            confidence = min(confidence + Decimal('0.05'), Decimal('1.0'))
        
        return confidence
    
    def _compile_results(
        self,
        matches: List[MatchResult],
        unmatched: List[PaymentLine],
        original_payments: List[PaymentLine],
        processing_time_ms: int
    ) -> Dict[str, Any]:
        """Compile comprehensive matching results"""
        
        total = len(original_payments)
        matched_count = len(matches)
        unmatched_count = len(unmatched)
        
        # Calculate pass statistics
        exact_count = len([m for m in matches if m.match_type == MatchingPassType.EXACT])
        relaxed_count = len([m for m in matches if m.match_type == MatchingPassType.RELAXED])
        numeric_count = len([m for m in matches if m.match_type == MatchingPassType.NUMERIC])
        
        match_percentage = Decimal(matched_count) / Decimal(total) * 100 if total > 0 else Decimal('0')
        
        summary = MatchingSummary(
            total_payments=total,
            matched_count=matched_count,
            unmatched_count=unmatched_count,
            match_percentage=match_percentage.quantize(Decimal('0.1')),
            all_matched=unmatched_count == 0,
            exact_matches=exact_count,
            relaxed_matches=relaxed_count,
            numeric_matches=numeric_count,
            processing_time_ms=processing_time_ms
        )
        
        return {
            'summary': summary.dict(),
            'matches': [match.dict() for match in matches],
            'unmatched': [{'id': str(p.id), 'reference': p.reference_number} for p in unmatched]
        }
    
    def _create_empty_result(self) -> Dict[str, Any]:
        """Result for empty payment list"""
        summary = MatchingSummary(
            total_payments=0,
            matched_count=0,
            unmatched_count=0,
            match_percentage=Decimal('0'),
            all_matched=True
        )
        return {'summary': summary.dict(), 'matches': [], 'unmatched': []}
    
    def _create_no_records_result(self, payments: List[PaymentLine]) -> Dict[str, Any]:
        """Result when no records available for matching"""
        summary = MatchingSummary(
            total_payments=len(payments),
            matched_count=0,
            unmatched_count=len(payments),
            match_percentage=Decimal('0'),
            all_matched=False
        )
        return {
            'summary': summary.dict(),
            'matches': [],
            'unmatched': [{'id': str(p.id), 'reference': p.reference_number} for p in payments]
        }
```

### 3. Database Integration Layer

Create database operations for your system:

```python
class MatchingDatabaseService:
    """Database operations for matching workflow"""
    
    def __init__(self, db_connection):
        self.db = db_connection
        self.logger = logging.getLogger(__name__)
    
    async def get_payments_for_matching(
        self,
        document_id: UUID,
        organization_id: UUID
    ) -> List[PaymentLine]:
        """Fetch payment lines that need matching"""
        try:
            # Customize this query for your database schema
            query = """
                SELECT id, reference_number, amount, description, matched_record_id
                FROM payment_lines 
                WHERE document_id = $1 AND organization_id = $2
                ORDER BY id
            """
            
            rows = await self.db.fetch(query, document_id, organization_id)
            
            return [
                PaymentLine(
                    id=UUID(row['id']),
                    reference_number=row['reference_number'],
                    amount=Decimal(str(row['amount'])),
                    description=row['description'],
                    matched_record_id=UUID(row['matched_record_id']) if row['matched_record_id'] else None
                )
                for row in rows
            ]
            
        except Exception as e:
            self.logger.error(f"Failed to fetch payments: {e}")
            raise
    
    async def get_records_for_matching(
        self,
        organization_id: UUID,
        record_type: str = "invoice"
    ) -> List[InvoiceRecord]:
        """Fetch records available for matching"""
        try:
            # Customize based on your record types and status filtering
            query = """
                SELECT id, reference_number, amount, status, organization_id
                FROM invoices 
                WHERE organization_id = $1 
                AND status != 'DELETED'
                ORDER BY reference_number
            """
            
            rows = await self.db.fetch(query, organization_id)
            
            return [
                InvoiceRecord(
                    id=UUID(row['id']),
                    reference_number=row['reference_number'],
                    amount=Decimal(str(row['amount'])),
                    status=row['status'],
                    organization_id=UUID(row['organization_id'])
                )
                for row in rows
            ]
            
        except Exception as e:
            self.logger.error(f"Failed to fetch records: {e}")
            raise
    
    async def save_matching_results(
        self,
        matches: List[MatchResult],
        organization_id: UUID
    ):
        """Save matching results to database"""
        if not matches:
            return
        
        try:
            # Update payment lines with matched record IDs
            for match in matches:
                query = """
                    UPDATE payment_lines 
                    SET 
                        matched_record_id = $1,
                        match_type = $2,
                        match_confidence = $3,
                        matched_at = NOW()
                    WHERE id = $4 AND organization_id = $5
                """
                
                await self.db.execute(
                    query,
                    match.matched_record_id,
                    match.match_type.value if match.match_type else None,
                    float(match.confidence),
                    match.payment_id,
                    organization_id
                )
            
            self.logger.info(f"Saved {len(matches)} matching results")
            
        except Exception as e:
            self.logger.error(f"Failed to save matches: {e}")
            raise
    
    async def log_matching_operation(
        self,
        document_id: UUID,
        organization_id: UUID,
        summary: Dict[str, Any]
    ):
        """Log matching operation for audit purposes"""
        try:
            query = """
                INSERT INTO matching_logs 
                (document_id, organization_id, total_payments, matched_count, 
                 match_percentage, processing_time_ms, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, NOW())
            """
            
            await self.db.execute(
                query,
                document_id,
                organization_id,
                summary['total_payments'],
                summary['matched_count'],
                float(summary['match_percentage']),
                summary['processing_time_ms']
            )
            
        except Exception as e:
            self.logger.warning(f"Failed to log matching operation: {e}")
            # Don't fail the main operation for logging errors
```

### 4. Complete Workflow Integration

Put together the complete workflow:

```python
class DocumentProcessingWorkflow:
    """Complete document processing with matching integration"""
    
    def __init__(
        self,
        matching_service: DocumentMatchingService,
        database_service: MatchingDatabaseService
    ):
        self.matching_service = matching_service
        self.database_service = database_service
        self.logger = logging.getLogger(__name__)
    
    async def process_document_with_matching(
        self,
        document_id: UUID,
        organization_id: UUID,
        user_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Complete document processing workflow with matching.
        
        Args:
            document_id: ID of document to process
            organization_id: Organization context
            user_context: User context for audit
            
        Returns:
            Processing result with matching statistics
        """
        try:
            # Step 1: Fetch payment data
            payments = await self.database_service.get_payments_for_matching(
                document_id, organization_id
            )
            
            if not payments:
                return {'status': 'no_payments', 'message': 'No payments found for matching'}
            
            # Step 2: Fetch available records
            records = await self.database_service.get_records_for_matching(
                organization_id
            )
            
            # Step 3: Execute matching
            self.logger.info(f"Starting matching for document {document_id}")
            matching_result = await self.matching_service.match_payments_to_records(
                payments, records, organization_id
            )
            
            # Step 4: Save results
            if matching_result['matches']:
                matches = [MatchResult(**match) for match in matching_result['matches']]
                await self.database_service.save_matching_results(
                    matches, organization_id
                )
            
            # Step 5: Log operation
            await self.database_service.log_matching_operation(
                document_id, organization_id, matching_result['summary']
            )
            
            # Step 6: Determine processing status
            summary = matching_result['summary']
            if summary['all_matched']:
                status = 'fully_matched'
            elif summary['matched_count'] > 0:
                status = 'partially_matched'
            else:
                status = 'unmatched'
            
            return {
                'status': status,
                'document_id': str(document_id),
                'summary': summary,
                'matches': len(matching_result['matches']),
                'unmatched': len(matching_result['unmatched'])
            }
            
        except Exception as e:
            self.logger.error(f"Document processing failed: {e}")
            return {
                'status': 'error',
                'document_id': str(document_id),
                'error': str(e)
            }
```

### 5. API Integration

Create REST API endpoints:

```python
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks

app = FastAPI()

@app.post("/api/documents/{document_id}/match")
async def match_document_payments(
    document_id: UUID,
    background_tasks: BackgroundTasks,
    workflow: DocumentProcessingWorkflow = Depends(get_workflow_service),
    user_context: dict = Depends(get_user_context)
):
    """Trigger matching for document payments"""
    
    try:
        # Run matching in background for large documents
        if user_context.get('async_processing', False):
            background_tasks.add_task(
                workflow.process_document_with_matching,
                document_id,
                user_context['organization_id'],
                user_context
            )
            return {'status': 'processing', 'message': 'Matching started in background'}
        else:
            # Synchronous processing for smaller documents
            result = await workflow.process_document_with_matching(
                document_id,
                user_context['organization_id'],
                user_context
            )
            return result
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/documents/{document_id}/matches")
async def get_document_matches(
    document_id: UUID,
    db_service: MatchingDatabaseService = Depends(get_database_service),
    user_context: dict = Depends(get_user_context)
):
    """Get matching results for a document"""
    
    payments = await db_service.get_payments_for_matching(
        document_id, 
        user_context['organization_id']
    )
    
    return {
        'document_id': str(document_id),
        'payments': [
            {
                'id': str(p.id),
                'reference': p.reference_number,
                'amount': float(p.amount),
                'matched': p.matched_record_id is not None,
                'matched_record_id': str(p.matched_record_id) if p.matched_record_id else None
            }
            for p in payments
        ]
    }
```

### 6. Configuration and Performance

Configure for your environment:

```python
from pydantic import BaseSettings

class MatchingConfig(BaseSettings):
    """Configuration for matching service"""
    
    # Performance settings
    batch_size: int = 1000
    max_cache_size: int = 10000
    matching_timeout_seconds: int = 300
    
    # Confidence thresholds
    min_confidence_threshold: float = 0.5
    exact_match_confidence: float = 0.95
    relaxed_match_confidence: float = 0.85
    numeric_match_confidence: float = 0.70
    
    # Database settings
    max_connections: int = 20
    query_timeout_seconds: int = 30
    
    class Config:
        env_prefix = "MATCHING_"

# Performance optimization tips
class OptimizedMatchingService(DocumentMatchingService):
    """Optimized version with performance enhancements"""
    
    def __init__(self, database_client, config: MatchingConfig):
        super().__init__(database_client)
        self.config = config
        self._record_cache = {}
        self._cache_expiry = None
    
    async def match_with_caching(
        self,
        payments: List[PaymentLine],
        organization_id: UUID
    ) -> Dict[str, Any]:
        """Matching with record caching for better performance"""
        
        # Check cache validity
        if self._should_refresh_cache():
            self._record_cache = {}
        
        # Use cached records if available
        cache_key = str(organization_id)
        if cache_key not in self._record_cache:
            records = await self.database_service.get_records_for_matching(organization_id)
            self._record_cache[cache_key] = records
            self._cache_expiry = asyncio.get_event_loop().time() + 300  # 5 min cache
        
        records = self._record_cache[cache_key]
        
        return await self.match_payments_to_records(payments, records, organization_id)
    
    def _should_refresh_cache(self) -> bool:
        """Check if cache should be refreshed"""
        return (
            self._cache_expiry is None or
            asyncio.get_event_loop().time() > self._cache_expiry or
            len(self._record_cache) > self.config.max_cache_size
        )
```

### 7. Testing Integration

Example test cases:

```python
import pytest
from unittest.mock import AsyncMock, Mock

@pytest.mark.asyncio
async def test_three_pass_matching():
    """Test the three-pass matching strategy"""
    
    # Mock database
    mock_db = AsyncMock()
    service = DocumentMatchingService(mock_db)
    
    # Test data
    payments = [
        PaymentLine(id=UUID4(), reference_number="INV-123", amount=Decimal('100')),
        PaymentLine(id=UUID4(), reference_number="inv 456", amount=Decimal('200')),
        PaymentLine(id=UUID4(), reference_number="BILL/789", amount=Decimal('300')),
    ]
    
    records = [
        InvoiceRecord(id=UUID4(), reference_number="INV-123", amount=Decimal('100'), status="ACTIVE", organization_id=UUID4()),
        InvoiceRecord(id=UUID4(), reference_number="INV-456", amount=Decimal('200'), status="ACTIVE", organization_id=UUID4()),
        InvoiceRecord(id=UUID4(), reference_number="BILL789", amount=Decimal('300'), status="ACTIVE", organization_id=UUID4()),
    ]
    
    # Execute matching
    result = await service.match_payments_to_records(payments, records, UUID4())
    
    # Verify results
    assert result['summary']['total_payments'] == 3
    assert result['summary']['matched_count'] == 3  # All should match with different strategies
    assert result['summary']['exact_matches'] == 1   # INV-123
    assert result['summary']['relaxed_matches'] == 2  # inv 456 -> INV456, BILL/789 -> BILL789

@pytest.mark.asyncio
async def test_partial_matching():
    """Test scenario with partial matches"""
    
    mock_db = AsyncMock()
    service = DocumentMatchingService(mock_db)
    
    payments = [
        PaymentLine(id=UUID4(), reference_number="MATCH-1", amount=Decimal('100')),
        PaymentLine(id=UUID4(), reference_number="NO-MATCH", amount=Decimal('200')),
    ]
    
    records = [
        InvoiceRecord(id=UUID4(), reference_number="MATCH-1", amount=Decimal('100'), status="ACTIVE", organization_id=UUID4()),
    ]
    
    result = await service.match_payments_to_records(payments, records, UUID4())
    
    assert result['summary']['total_payments'] == 2
    assert result['summary']['matched_count'] == 1
    assert result['summary']['unmatched_count'] == 1
    assert not result['summary']['all_matched']
```

This comprehensive integration guide provides everything needed to implement RemitMatch's invoice matching workflow in your own applications. Adapt the data models, database operations, and business logic to match your specific requirements while maintaining the core three-pass matching strategy for optimal results.