# Invoice Matching Workflow Troubleshooting Guide

## Common Issues and Solutions

This guide covers common issues encountered when implementing or using the invoice matching workflow, along with detailed solutions and debugging strategies.

## 1. Matching Performance Issues

### Problem: Slow Matching Performance
**Symptoms:**
- Matching takes longer than expected (>30 seconds for <1000 records)
- High CPU usage during matching operations
- Database connection timeouts

**Causes & Solutions:**

#### Large Dataset Issues
```python
# Problem: Loading too many records into memory
async def inefficient_matching(self, organization_id):
    # DON'T DO THIS - loads everything at once
    invoices = await self.db.fetch("SELECT * FROM invoices WHERE org_id = $1", org_id)
    
# Solution: Implement pagination and filtering
async def efficient_matching(self, organization_id):
    # Filter out unnecessary records
    query = """
        SELECT id, invoice_number, amount, status 
        FROM invoices 
        WHERE organization_id = $1 
        AND status NOT IN ('DELETED', 'CANCELLED')
        AND created_at > NOW() - INTERVAL '2 years'
        LIMIT 10000
    """
    invoices = await self.db.fetch(query, organization_id)
```

#### Database Index Issues
```sql
-- Ensure proper indexing for performance
CREATE INDEX CONCURRENTLY idx_invoices_org_status 
ON invoices(organization_id, status) 
WHERE status != 'DELETED';

CREATE INDEX CONCURRENTLY idx_invoices_number_upper 
ON invoices(UPPER(invoice_number));

CREATE INDEX CONCURRENTLY idx_remittance_lines_remittance 
ON remittance_lines(remittance_id);
```

#### Memory Optimization
```python
class OptimizedMatchingService:
    def __init__(self, db_client):
        self.db = db_client
        self.batch_size = 500  # Process in smaller batches
        self.lookup_cache = {}
        self.cache_limit = 5000
    
    def _build_invoice_lookup(self, invoices, normalizer_func):
        """Optimized lookup building with memory management"""
        lookup = {}
        
        # Clear cache if too large
        if len(self.lookup_cache) > self.cache_limit:
            self.lookup_cache.clear()
        
        for invoice in invoices:
            invoice_number = invoice.get('invoice_number', '')
            if not invoice_number:
                continue
            
            # Cache normalization results
            cache_key = f"{normalizer_func.__name__}:{invoice_number}"
            if cache_key in self.lookup_cache:
                normalized = self.lookup_cache[cache_key]
            else:
                normalized = normalizer_func(invoice_number)
                self.lookup_cache[cache_key] = normalized
            
            if normalized and normalized not in lookup:
                lookup[normalized] = invoice
        
        return lookup
```

### Problem: Database Connection Issues
**Symptoms:**
- Connection timeouts during matching
- "Connection closed" errors
- Pool exhaustion warnings

**Solution:**
```python
import asyncio
from contextlib import asynccontextmanager

class DatabaseManager:
    def __init__(self, connection_pool):
        self.pool = connection_pool
        self.max_retries = 3
        self.retry_delay = 1.0
    
    @asynccontextmanager
    async def get_connection(self):
        """Connection manager with retry logic"""
        connection = None
        for attempt in range(self.max_retries):
            try:
                connection = await self.pool.acquire()
                yield connection
                return
            except Exception as e:
                if connection:
                    await self.pool.release(connection)
                if attempt == self.max_retries - 1:
                    raise
                await asyncio.sleep(self.retry_delay * (2 ** attempt))
        
        finally:
            if connection:
                await self.pool.release(connection)

# Usage in matching service
async def fetch_invoices_with_retry(self, organization_id):
    async with self.db_manager.get_connection() as conn:
        return await conn.fetch(query, organization_id)
```

## 2. Matching Accuracy Issues

### Problem: Low Matching Rates
**Symptoms:**
- Expected matches not being found
- High number of unmatched payment lines
- Manual overrides frequently needed

**Diagnostic Steps:**

#### 1. Analyze Invoice Number Formats
```python
async def analyze_invoice_formats(self, organization_id):
    """Analyze invoice number patterns to optimize normalization"""
    
    # Get sample of invoice numbers
    query = "SELECT DISTINCT invoice_number FROM invoices WHERE organization_id = $1 LIMIT 100"
    results = await self.db.fetch(query, organization_id)
    
    patterns = {
        'exact_matches': 0,
        'case_issues': 0,
        'whitespace_issues': 0,
        'punctuation_issues': 0,
        'numeric_only': 0,
        'complex_format': 0
    }
    
    for row in results:
        invoice_num = row['invoice_number']
        
        # Analyze patterns
        if invoice_num.isdigit():
            patterns['numeric_only'] += 1
        elif invoice_num != invoice_num.strip():
            patterns['whitespace_issues'] += 1
        elif invoice_num != invoice_num.upper():
            patterns['case_issues'] += 1
        elif any(char in invoice_num for char in '-/_#.:'):
            patterns['punctuation_issues'] += 1
        else:
            patterns['complex_format'] += 1
    
    return patterns
```

#### 2. Test Normalization Effectiveness
```python
async def test_normalization_strategies(self, payment_lines, invoices):
    """Test which normalization strategy works best for your data"""
    
    strategies = ['exact', 'relaxed', 'numeric']
    results = {}
    
    for strategy in strategies:
        normalizer = getattr(self, f'_{strategy}_normalize')
        
        # Build lookup
        invoice_lookup = self._build_invoice_lookup(invoices, normalizer)
        
        # Test matching
        matches = 0
        for line in payment_lines:
            normalized = normalizer(line['invoice_number'])
            if normalized in invoice_lookup:
                matches += 1
        
        results[strategy] = {
            'matches': matches,
            'rate': matches / len(payment_lines) if payment_lines else 0
        }
    
    return results
```

#### 3. Custom Normalization for Specific Formats
```python
def custom_normalize_for_organization(self, invoice_number, org_patterns):
    """Custom normalization based on organization-specific patterns"""
    
    if not invoice_number:
        return ""
    
    normalized = invoice_number.strip().upper()
    
    # Apply organization-specific rules
    if org_patterns.get('remove_prefix'):
        # Remove common prefixes like "INVOICE-", "BILL-"
        for prefix in org_patterns['remove_prefix']:
            if normalized.startswith(prefix.upper()):
                normalized = normalized[len(prefix):].lstrip('-_/')
    
    if org_patterns.get('zero_pad'):
        # Zero pad numbers to consistent length
        if normalized.isdigit():
            normalized = normalized.zfill(org_patterns['zero_pad'])
    
    if org_patterns.get('standardize_separators'):
        # Replace all separators with standard one
        for sep in ['-', '_', '/', '\\', '.', ':', ' ']:
            normalized = normalized.replace(sep, '-')
    
    return normalized
```

### Problem: False Positive Matches
**Symptoms:**
- Incorrect matches being made
- Same invoice matched to multiple payments
- Confidence scores don't reflect match quality

**Solutions:**

#### 1. Implement Additional Validation
```python
def validate_match_quality(self, payment, invoice, match_type):
    """Additional validation for match quality"""
    
    issues = []
    confidence_adjustments = []
    
    # Amount validation
    if hasattr(payment, 'amount') and hasattr(invoice, 'amount'):
        amount_diff = abs(payment.amount - invoice.amount)
        amount_ratio = amount_diff / invoice.amount if invoice.amount > 0 else 1
        
        if amount_ratio > 0.1:  # More than 10% difference
            issues.append(f"Amount mismatch: payment ${payment.amount}, invoice ${invoice.amount}")
            confidence_adjustments.append(-0.2)
    
    # Date validation
    if hasattr(payment, 'date') and hasattr(invoice, 'date'):
        date_diff = abs((payment.date - invoice.date).days)
        if date_diff > 90:  # More than 90 days apart
            issues.append(f"Date mismatch: {date_diff} days apart")
            confidence_adjustments.append(-0.1)
    
    # Reference validation for numeric matches
    if match_type == MatchingPassType.NUMERIC:
        payment_digits = ''.join(c for c in payment.reference_number if c.isdigit())
        invoice_digits = ''.join(c for c in invoice.reference_number if c.isdigit())
        
        if len(payment_digits) != len(invoice_digits):
            issues.append("Different digit lengths in numeric match")
            confidence_adjustments.append(-0.1)
    
    return issues, sum(confidence_adjustments)
```

#### 2. Implement Duplicate Prevention
```python
class DuplicatePreventionMatcher(DocumentMatchingService):
    def __init__(self, database_client):
        super().__init__(database_client)
        self.used_invoices = set()
    
    def _match_with_lookup(self, payments, invoice_lookup, normalizer_func, pass_type):
        """Enhanced matching with duplicate prevention"""
        matches = []
        unmatched = []
        
        for payment in payments:
            if not payment.reference_number:
                unmatched.append(payment)
                continue
            
            normalized_ref = normalizer_func(payment.reference_number)
            
            if normalized_ref in invoice_lookup:
                invoice = invoice_lookup[normalized_ref]
                
                # Check if invoice already used
                if invoice['id'] in self.used_invoices:
                    # Find alternative or mark as unmatched
                    unmatched.append(payment)
                    continue
                
                # Validate match quality
                issues, confidence_adj = self.validate_match_quality(payment, invoice, pass_type)
                
                if not issues or len(issues) <= 1:  # Accept matches with minor issues
                    self.used_invoices.add(invoice['id'])
                    
                    base_confidence = self._calculate_confidence(pass_type, payment, invoice)
                    adjusted_confidence = max(base_confidence + Decimal(str(confidence_adj)), Decimal('0.1'))
                    
                    match = MatchResult(
                        payment_id=payment.id,
                        payment_reference=payment.reference_number,
                        matched_invoice_id=UUID(invoice['id']),
                        matched_invoice_number=invoice['invoice_number'],
                        match_type=pass_type,
                        confidence=adjusted_confidence
                    )
                    matches.append(match)
                else:
                    unmatched.append(payment)
            else:
                unmatched.append(payment)
        
        return matches, unmatched
```

## 3. Data Quality Issues

### Problem: Inconsistent Invoice Numbering
**Symptoms:**
- Same logical invoice has different numbers in different systems
- Invoice numbers with inconsistent formatting
- Missing or empty invoice numbers

**Solutions:**

#### 1. Data Quality Analysis
```python
async def analyze_data_quality(self, organization_id):
    """Comprehensive data quality analysis"""
    
    issues = {
        'empty_invoice_numbers': 0,
        'duplicate_invoice_numbers': 0,
        'inconsistent_formatting': 0,
        'unusual_characters': 0,
        'length_variations': {}
    }
    
    # Analyze invoice numbers
    query = "SELECT invoice_number FROM invoices WHERE organization_id = $1"
    results = await self.db.fetch(query, organization_id)
    
    invoice_numbers = [r['invoice_number'] for r in results if r['invoice_number']]
    
    # Check for issues
    for inv_num in invoice_numbers:
        if not inv_num or not inv_num.strip():
            issues['empty_invoice_numbers'] += 1
            continue
        
        # Length analysis
        length = len(inv_num)
        issues['length_variations'][length] = issues['length_variations'].get(length, 0) + 1
        
        # Character analysis
        unusual_chars = set(inv_num) - set(string.ascii_letters + string.digits + '-_/\\.:# ')
        if unusual_chars:
            issues['unusual_characters'] += 1
    
    # Check for duplicates
    from collections import Counter
    counts = Counter(invoice_numbers)
    issues['duplicate_invoice_numbers'] = len([inv for inv, count in counts.items() if count > 1])
    
    return issues
```

#### 2. Data Cleaning Pipeline
```python
class DataCleaningService:
    def __init__(self):
        self.cleaning_rules = []
    
    def add_cleaning_rule(self, rule_func, description):
        """Add custom cleaning rule"""
        self.cleaning_rules.append((rule_func, description))
    
    def clean_invoice_number(self, invoice_number, organization_rules=None):
        """Apply cleaning rules to invoice number"""
        if not invoice_number:
            return invoice_number
        
        cleaned = invoice_number
        applied_rules = []
        
        # Standard cleaning rules
        rules = [
            (lambda x: x.strip(), "trim_whitespace"),
            (lambda x: re.sub(r'\s+', ' ', x), "normalize_whitespace"),
            (lambda x: x.upper(), "uppercase"),
        ]
        
        # Add organization-specific rules
        if organization_rules:
            rules.extend(organization_rules)
        
        # Add custom rules
        rules.extend(self.cleaning_rules)
        
        for rule_func, description in rules:
            try:
                new_value = rule_func(cleaned)
                if new_value != cleaned:
                    applied_rules.append(description)
                    cleaned = new_value
            except Exception as e:
                logging.warning(f"Cleaning rule '{description}' failed: {e}")
        
        return cleaned, applied_rules

# Usage
cleaner = DataCleaningService()

# Add custom rule for specific organization
def remove_invoice_prefix(invoice_num):
    if invoice_num.startswith('INVOICE-'):
        return invoice_num[8:]
    return invoice_num

cleaner.add_cleaning_rule(remove_invoice_prefix, "remove_invoice_prefix")
```

## 4. Configuration and Environment Issues

### Problem: Different Behavior Across Environments
**Symptoms:**
- Matching works in dev but not production
- Different match rates between environments
- Inconsistent normalization results

**Solutions:**

#### 1. Environment Configuration Validation
```python
class EnvironmentValidator:
    def __init__(self, config):
        self.config = config
    
    async def validate_environment(self):
        """Validate environment configuration"""
        issues = []
        
        # Database connectivity
        try:
            await self.config.database.fetch("SELECT 1")
        except Exception as e:
            issues.append(f"Database connection failed: {e}")
        
        # Data consistency
        try:
            count_query = "SELECT COUNT(*) FROM invoices"
            result = await self.config.database.fetch(count_query)
            if result[0]['count'] == 0:
                issues.append("No invoices found in database")
        except Exception as e:
            issues.append(f"Data validation failed: {e}")
        
        # Configuration validation
        if not hasattr(self.config, 'matching_batch_size'):
            issues.append("Missing matching_batch_size configuration")
        
        if self.config.matching_batch_size > 10000:
            issues.append("Batch size too large, may cause memory issues")
        
        return issues
```

#### 2. Logging and Monitoring
```python
import structlog

class MatchingServiceWithLogging(DocumentMatchingService):
    def __init__(self, database_client):
        super().__init__(database_client)
        self.logger = structlog.get_logger(__name__)
    
    async def match_payments_to_records(self, payments, records, organization_id):
        """Enhanced matching with comprehensive logging"""
        
        # Log input parameters
        self.logger.info(
            "matching_started",
            organization_id=str(organization_id),
            payment_count=len(payments),
            record_count=len(records),
            payment_sample=[p.reference_number[:20] for p in payments[:5]]
        )
        
        start_time = asyncio.get_event_loop().time()
        
        try:
            result = await super().match_payments_to_records(payments, records, organization_id)
            
            processing_time = int((asyncio.get_event_loop().time() - start_time) * 1000)
            
            # Log results
            self.logger.info(
                "matching_completed",
                organization_id=str(organization_id),
                total_payments=result['summary']['total_payments'],
                matched_count=result['summary']['matched_count'],
                match_rate=f"{result['summary']['match_percentage']:.1f}%",
                exact_matches=result['summary']['exact_matches'],
                relaxed_matches=result['summary']['relaxed_matches'],
                numeric_matches=result['summary']['numeric_matches'],
                processing_time_ms=processing_time
            )
            
            return result
            
        except Exception as e:
            self.logger.error(
                "matching_failed",
                organization_id=str(organization_id),
                error=str(e),
                payment_count=len(payments),
                record_count=len(records)
            )
            raise
```

## 5. Debugging Tools and Utilities

### Debug Matching Results
```python
class MatchingDebugger:
    def __init__(self, matching_service):
        self.service = matching_service
    
    async def debug_matching_failure(self, payment_reference, organization_id):
        """Debug why a specific payment didn't match"""
        
        # Get all invoices for organization
        invoices = await self.service.database_service.get_records_for_matching(organization_id)
        
        print(f"Debugging payment reference: '{payment_reference}'")
        print(f"Available invoices: {len(invoices)}")
        
        # Test each normalization strategy
        strategies = [
            (self.service._exact_normalize, "Exact"),
            (self.service._relaxed_normalize, "Relaxed"),
            (self.service._numeric_normalize, "Numeric")
        ]
        
        for normalizer, strategy_name in strategies:
            normalized_payment = normalizer(payment_reference)
            print(f"\n{strategy_name} normalization: '{payment_reference}' -> '{normalized_payment}'")
            
            # Build lookup
            lookup = self.service._build_invoice_lookup(invoices, normalizer)
            
            if normalized_payment in lookup:
                matched_invoice = lookup[normalized_payment]
                print(f"  ✓ Match found: {matched_invoice['invoice_number']}")
                return
            else:
                # Show close matches
                close_matches = [
                    (norm_inv, inv_data['invoice_number']) 
                    for norm_inv, inv_data in lookup.items()
                    if self._is_similar(normalized_payment, norm_inv)
                ]
                
                if close_matches:
                    print(f"  ✗ No exact match, but similar invoices found:")
                    for norm, orig in close_matches[:5]:
                        print(f"    {orig} -> {norm}")
                else:
                    print(f"  ✗ No match or similar invoices found")
        
        print(f"\nSample invoice numbers for comparison:")
        for invoice in invoices[:10]:
            print(f"  {invoice['invoice_number']}")
    
    def _is_similar(self, str1, str2, threshold=0.8):
        """Check if two strings are similar using Levenshtein distance"""
        if not str1 or not str2:
            return False
        
        # Simple similarity check - implement proper algorithm as needed
        longer = max(len(str1), len(str2))
        if longer == 0:
            return True
        
        # Calculate simple character overlap
        common_chars = set(str1) & set(str2)
        similarity = len(common_chars) / len(set(str1) | set(str2))
        
        return similarity >= threshold

# Usage
debugger = MatchingDebugger(matching_service)
await debugger.debug_matching_failure("INV-123", organization_id)
```

This troubleshooting guide provides comprehensive solutions for common issues encountered with the invoice matching workflow. Use these debugging tools and solutions to optimize matching performance and accuracy for your specific use case.