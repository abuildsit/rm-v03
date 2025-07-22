# Invoice Matching Workflow Documentation

## Overview

RemitMatch's invoice matching workflow implements a sophisticated three-pass matching engine that automatically correlates extracted payment data against stored invoices. The system uses progressive normalization strategies to maximize matching accuracy while maintaining high performance.

## Architecture

```
Payment Data → Three-Pass Matching → Database Updates → Status Determination
```

### Key Components

- **InvoiceMatchingService**: Core matching engine with three-pass strategy
- **Normalization Functions**: Progressive text normalization (exact → relaxed → numeric)
- **Database Integration**: Efficient O(1) lookups and batch updates
- **Performance Optimization**: Early termination and lookup tables

## Three-Pass Strategy

1. **Pass 1 - Exact Match**: `trim().toUpperCase()` - handles case and whitespace variations
2. **Pass 2 - Relaxed Match**: Remove non-alphanumeric characters - handles punctuation differences  
3. **Pass 3 - Numeric Match**: Extract digits only - handles heavily formatted invoice numbers

## Workflow Steps

1. **Data Fetching**: Retrieve payment lines and organization invoices
2. **Progressive Matching**: Apply three normalization passes sequentially
3. **Database Updates**: Batch update matched invoice IDs
4. **Result Compilation**: Generate comprehensive matching statistics

## Code Examples

See the `code-examples/` directory for detailed implementation patterns:

- `invoice-matching-service.py`: Complete matching service implementation
- `normalization-functions.py`: Text normalization strategies
- `database-operations.py`: Efficient data retrieval and updates
- `performance-optimizations.py`: Lookup tables and batch processing

## Performance Characteristics

- **O(1) Matching**: Dictionary-based lookups for each normalization pass
- **Early Termination**: Stops when all lines are matched
- **Batch Operations**: Single database update for all matches
- **Memory Efficient**: Processes data in streams, not loaded entirely in memory

## Integration Points

The matching service integrates seamlessly with:
- **Remittance Processing Pipeline**: Automatic matching after AI extraction
- **Manual Override System**: Support for user corrections via `override_invoice_id`
- **Status Management**: Updates remittance status based on matching success
- **Audit System**: Comprehensive logging and tracking

## Data Models

### Input Data
- **Remittance Lines**: Individual payment records with invoice numbers
- **Organization Invoices**: Cached invoice data from external systems (e.g., Xero)

### Output Data
- **Match Results**: Detailed matching outcome per payment line
- **Summary Statistics**: Aggregate matching metrics and pass-type breakdown
- **Updated Records**: Database records with matched invoice IDs

## Configuration

### Matching Rules
- **First Match Wins**: No duplicate matching within same pass
- **Organization Isolation**: Multi-tenant support with strict organization context
- **Status Filtering**: Excludes deleted/invalid invoices from matching

### Performance Tuning
- **Lookup Table Size**: Optimized for typical invoice volumes (1K-10K invoices)
- **Memory Usage**: Efficient normalization with minimal string operations
- **Database Connections**: Uses connection pooling for high throughput

## Error Handling

The system provides comprehensive error handling including:
- **Data Validation**: Input validation for payment lines and invoices
- **Database Errors**: Graceful handling of connection and query failures
- **Performance Monitoring**: Tracking of matching times and success rates
- **Detailed Logging**: Complete audit trail for troubleshooting

## Troubleshooting

Common scenarios and solutions documented in `troubleshooting.md`.