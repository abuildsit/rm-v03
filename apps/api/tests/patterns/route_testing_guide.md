# Route Testing Standards

## Recommended Pattern

Instead of using TestClient (which has authentication complications), follow this pattern used by successful domain tests:

```python
@pytest.mark.asyncio
@patch("src.domains.DOMAIN.routes.service_function")
@patch("src.domains.DOMAIN.routes.require_permission")
async def test_route_success(
    self,
    mock_require_permission,
    mock_service_function,
    mock_organization_member_admin,
):
    """Test route logic directly without HTTP layer."""
    # Mock permission check
    mock_require_permission.return_value = lambda: mock_organization_member_admin
    
    # Mock service response
    mock_service_function.return_value = expected_response
    
    # Call route function directly
    from src.domains.DOMAIN.routes import route_function
    result = await route_function(
        org_id="test-org-123",
        membership=mock_organization_member_admin,
        db=mock_db,
        # ... other parameters
    )
    
    # Assert results
    assert result == expected_response
    mock_service_function.assert_called_once_with(...)
```

## Why This Pattern?

1. **No Auth Complexity**: Bypasses FastAPI's authentication middleware
2. **Direct Testing**: Tests the actual route logic, not HTTP infrastructure  
3. **Consistent**: Matches patterns in bankaccounts, organizations domains
4. **Fast**: No HTTP overhead
5. **Reliable**: No dependency on auth token generation

## Permission Testing

Use parametrized tests for permission scenarios:

```python
@pytest.mark.parametrize("role,should_have_access", [
    (OrganizationRole.owner, True),
    (OrganizationRole.admin, True), 
    (OrganizationRole.auditor, False),
    (OrganizationRole.user, False),
])
def test_permission_by_role(self, role, should_have_access):
    # Test permission logic
```

This approach makes tests resilient to new permissions and roles.