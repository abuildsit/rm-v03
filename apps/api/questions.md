# Questions for Tomorrow

## Critical Issues Found During Implementation

### 1. Test Framework Issues
- Several tests are failing due to AsyncMock usage that prevents proper await operations
- The error "object AsyncMock can't be used in 'await' expression" suggests test fixture issues
- Need to review test mocking patterns for async functions

### 2. Method Signature Changes
- Updated `get_invoices` method signature with optional `invoice_id` parameter
- Some existing tests need to be updated to match the new signature
- All calls are backward compatible but tests may need parameter adjustments

### 3. Potential Enhancements
- Should we add retry logic for file upload failures?
- Do we want metrics/monitoring for the async tasks?
- Should we add a database field to track attachment upload status?

## Status
- ✅ All new functionality implemented
- ✅ Linting and type checking passes
- ❌ 12 test failures need to be resolved
- Tests are failing on mocking issues, not actual logic problems

## Next Steps
1. Fix AsyncMock usage in tests
2. Update test method signatures to match new interface
3. Verify end-to-end functionality manually