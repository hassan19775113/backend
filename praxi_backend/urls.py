"""PraxiApp URL Configuration.

API-Routen:
    /api/auth/         - Authentication (core)
    /api/health/       - Health check (core)
    /api/appointments/ - Termine (appointments)
    /api/operations/   - OPs (appointments)
    /api/patients/     - Patienten-Cache (patients)
    /api/medical/      - Legacy-Patienten-DB (medical)
"""

from django.conf import settings
from django.contrib import admin
from django.http import HttpResponse
from django.shortcuts import render
from django.urls import include, path

from praxi_backend.core.admin import praxi_admin_site


def root(request):
    """Root endpoint.

    - For browsers (Accept: text/html) in DEBUG mode, show a small index page with links.
    - For non-HTML clients, keep a stable plain-text response (acts like a simple healthcheck).
    """

    accept = request.headers.get("Accept", "")
    wants_html = "text/html" in accept.lower()
    if getattr(settings, "DEBUG", False) and wants_html:
        return render(request, "index.html")

    return HttpResponse("PraxiApp backend is running.")


urlpatterns = [
    # Root & Admin
    path("", root, name="root"),
    path("admin/", admin.site.urls),  # Standard Django Admin
    path("praxiadmin/dashboard/", include("praxi_backend.dashboard.urls")),  # Dashboard (MUSS VOR praxiadmin/ stehen!)
    path("praxiadmin/", praxi_admin_site.urls),  # Custom PraxiApp Admin

    # API Routes - Order matters!
    path("api/", include("praxi_backend.core.urls")),
    path("api/", include("praxi_backend.appointments.urls")),
    path("api/", include("praxi_backend.patients.urls")),
    path("api/medical/", include("praxi_backend.medical.urls")),
]