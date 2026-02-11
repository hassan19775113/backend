from __future__ import annotations

from django.http import HttpResponse
from django.test import TestCase, override_settings
from praxi_backend.dashboard.permissions import dashboard_access_required


class DashboardPermissionsTest(TestCase):
    """Unit tests for dashboard access decorator.

    The bypass behavior is explicitly controlled via the
    `DASHBOARD_AUTH_BYPASS_FOR_TESTS` settings flag.
    """

    databases = {"default"}

    @override_settings(DASHBOARD_AUTH_BYPASS_FOR_TESTS=True)
    def test_dashboard_access_required_is_noop_when_bypass_enabled(self):
        def view(request):
            return HttpResponse("ok")

        decorated = dashboard_access_required(view)
        self.assertIs(decorated, view)

    @override_settings(DASHBOARD_AUTH_BYPASS_FOR_TESTS=False)
    def test_dashboard_access_required_wraps_when_bypass_disabled(self):
        def view(request):
            return HttpResponse("ok")

        decorated = dashboard_access_required(view)
        self.assertIsNot(decorated, view)
