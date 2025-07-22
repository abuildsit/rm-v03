"""
Helper utilities for standardized route testing across domains.
"""

from typing import Any, Callable, Dict, Optional
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient
from prisma.enums import OrganizationRole
from prisma.models import OrganizationMember


class RouteTestHelper:
    """
    Helper class for standardized route testing patterns.

    Provides consistent authentication mocking and test patterns
    that work across all domains.
    """

    @staticmethod
    def mock_auth_dependency(
        mock_member: Mock, permission_path: str = "require_permission"
    ) -> Callable:
        """
        Create a mock auth dependency that returns the given member.

        Args:
            mock_member: Mock OrganizationMember to return
            permission_path: Path to the require_permission import to patch

        Returns:
            Function that can be used as a dependency override
        """
        return lambda: mock_member

    @staticmethod
    def create_mock_member(
        role: OrganizationRole = OrganizationRole.admin,
        org_id: str = "test-org-123",
        member_id: str = "test-member-123",
        profile_id: str = "test-profile-123",
    ) -> Mock:
        """Create a mock OrganizationMember with standard test values."""
        member = Mock(spec=OrganizationMember)
        member.id = member_id
        member.profileId = profile_id
        member.organizationId = org_id
        member.role = role
        return member

    @staticmethod
    def test_route_with_auth(
        client: TestClient,
        method: str,
        url: str,
        mock_member: Mock,
        service_patches: Optional[Dict[str, Any]] = None,
        request_data: Optional[Dict[str, Any]] = None,
        files: Optional[Dict[str, Any]] = None,
        auth_headers: Optional[Dict[str, str]] = None,
    ) -> Any:
        """
        Test a route with proper authentication and service mocking.

        Args:
            client: TestClient instance
            method: HTTP method (get, post, patch, etc.)
            url: URL to test
            mock_member: Mock member for authentication
            service_patches: Dict of service functions to patch
            request_data: JSON data for request
            files: Files for multipart requests
            auth_headers: Authentication headers

        Returns:
            Response from the test client
        """
        # Default auth headers if not provided
        if auth_headers is None:
            auth_headers = {"Authorization": "Bearer test-token"}

        # Set up service patches
        patches = []
        if service_patches:
            for patch_path, mock_return in service_patches.items():
                if isinstance(mock_return, Exception):
                    patches.append(patch(patch_path, side_effect=mock_return))
                else:
                    patches.append(patch(patch_path, return_value=mock_return))

        # Apply all patches
        for p in patches:
            p.start()

        try:
            # Make the request
            client_method = getattr(client, method.lower())
            kwargs = {"headers": auth_headers}

            if request_data:
                kwargs["json"] = request_data
            if files:
                kwargs["files"] = files

            return client_method(url, **kwargs)
        finally:
            # Clean up patches
            for p in patches:
                p.stop()


def create_permission_test_cases():
    """
    Create standardized permission test cases for route testing.

    Returns list of test cases with (role, should_have_access) tuples
    for common permission scenarios.
    """
    return [
        (OrganizationRole.owner, True),
        (OrganizationRole.admin, True),
        (OrganizationRole.auditor, False),  # Typically read-only
        (OrganizationRole.user, False),  # Typically limited access
    ]


def create_view_permission_test_cases():
    """
    Create test cases for view/read permissions.

    Most roles should have view access.
    """
    return [
        (OrganizationRole.owner, True),
        (OrganizationRole.admin, True),
        (OrganizationRole.auditor, True),  # Auditors can view
        (OrganizationRole.user, True),  # Users can often view
    ]
