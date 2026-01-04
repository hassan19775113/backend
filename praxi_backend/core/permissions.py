"""Core permissions for RBAC (Role-Based Access Control).

This module provides base permission classes and role-specific permissions
following the project's RBAC pattern with read_roles/write_roles.

Standard roles: admin, assistant, doctor, billing
"""

from rest_framework.permissions import BasePermission, SAFE_METHODS


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

    def _role_name(self, request):
        user = getattr(request, "user", None)
        role = getattr(user, "role", None)
        return getattr(role, "name", None)

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
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
        if not getattr(user, 'role', None):
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
