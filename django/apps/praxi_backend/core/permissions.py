"""Core permissions for RBAC (Role-Based Access Control).

This module provides base permission classes and role-specific permissions
following the project's RBAC pattern with read_roles/write_roles.

Standard roles: admin, assistant, doctor, billing
"""

from rest_framework.permissions import SAFE_METHODS, BasePermission


def is_running_tests() -> bool:
    """Detect test runs.

    Prefer an explicit settings flag (set by the test runner) so behavior is
    deterministic and does not depend on argv.
    """
    try:
        from django.conf import settings

        if getattr(settings, "configured", False):
            return bool(getattr(settings, "PRAXI_RUNNING_TESTS", False))
    except Exception:
        # Fall back to argv when Django isn't configured (e.g., importing this
        # module in tooling contexts).
        pass

    import sys

    argv = {str(a).lower() for a in sys.argv}
    return bool({"test", "pytest"} & argv)


class RBACPermission(BasePermission):
    """Base class for RBAC permissions with read_roles/write_roles pattern.

    Subclasses should define:
    - read_roles: set of role names that can perform GET/HEAD/OPTIONS
    - write_roles: set of role names that can perform POST/PUT/PATCH/DELETE

    Example:
        class MyPermission(RBACPermission):
            read_roles = {"admin", "assistant", "doctor", "billing"}
            write_roles = {"admin", "assistant"}
    """

    read_roles: set = set()
    write_roles: set = set()

    # Explicitly configurable overrides.
    # NOTE: Defaults are False to avoid changing existing behavior implicitly.
    treat_staff_as_admin: bool = False
    treat_superuser_as_admin: bool = False

    def _is_authenticated(self, request) -> bool:
        user = getattr(request, "user", None)
        return bool(user and getattr(user, "is_authenticated", False))

    def _user_is_staff_admin(self, user) -> bool:
        return bool(self.treat_staff_as_admin and getattr(user, "is_staff", False))

    def _user_is_superuser_admin(self, user) -> bool:
        return bool(self.treat_superuser_as_admin and getattr(user, "is_superuser", False))

    def _resolve_role_name(self, user):
        if user is None:
            return None
        if self._user_is_superuser_admin(user) or self._user_is_staff_admin(user):
            return "admin"
        role = getattr(user, "role", None)
        return getattr(role, "name", None)

    def _role_name(self, request):
        user = getattr(request, "user", None)
        return self._resolve_role_name(user)

    def has_permission(self, request, view):
        if not self._is_authenticated(request):
            return False

        role_name = self._role_name(request)
        if not role_name:
            return False

        if request.method in SAFE_METHODS:
            return role_name in self.read_roles

        return role_name in self.write_roles

    def has_object_permission(self, request, view, obj):
        # Default: same as has_permission
        # Subclasses can override for object-level checks (e.g., doctor owns record)
        return True


class IsRole(BasePermission):
    """Legacy base class for simple role checks.

    Note: For new code, prefer RBACPermission with read_roles/write_roles.
    """

    allowed_roles: list = []

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if not getattr(user, "role", None):
            return False
        return user.role.name in self.allowed_roles


class IsAdmin(IsRole):
    """Permission: user must have admin role."""

    allowed_roles = ["admin"]


class IsDoctor(IsRole):
    """Permission: user must have doctor role."""

    allowed_roles = ["doctor"]


class IsAssistant(IsRole):
    """Permission: user must have assistant role."""

    allowed_roles = ["assistant"]


class IsBilling(IsRole):
    """Permission: user must have billing role."""

    allowed_roles = ["billing"]
