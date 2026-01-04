from rest_framework.permissions import BasePermission, SAFE_METHODS


class PatientPermission(BasePermission):
    """RBAC for Patient endpoints (system database cache).

    - admin: full access (read + write)
    - assistant: full access (read + write)
    - doctor: full access (read + write)
    - billing: read-only
    """

    read_roles = {"admin", "assistant", "doctor", "billing"}
    write_roles = {"admin", "assistant", "doctor"}

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
        role_name = self._role_name(request)
        if not role_name:
            return False

        # Billing can only read
        if role_name == "billing" and request.method not in SAFE_METHODS:
            return False

        return True
