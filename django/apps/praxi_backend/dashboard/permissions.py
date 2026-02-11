"""Permission/decorator helpers for dashboard views.

The dashboard app mixes Django TemplateViews and JSON endpoints.

Phase 3 goal: unify access-control usage across views.

Important stability note:
- Some existing unit tests render dashboard views via RequestFactory without authentication.
  Those tests can opt into bypassing staff checks via a settings flag.
- Outside that explicitly-enabled mode, dashboard pages remain staff-only.
"""

from __future__ import annotations

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required


def _bypass_staff_checks() -> bool:
  return bool(getattr(settings, "DASHBOARD_AUTH_BYPASS_FOR_TESTS", False))


def dashboard_access_required(view_func):
    """Decorator: staff-only outside tests; no-op during tests.

    Use with `@method_decorator(dashboard_access_required)` on CBVs.
    """
    if _bypass_staff_checks():
        return view_func
    return staff_member_required(view_func)


def staff_required(view_func):
    """Alias kept for backward compatibility.

    Prefer `dashboard_access_required` for new/modernized views.
    """
    return staff_member_required(view_func)
