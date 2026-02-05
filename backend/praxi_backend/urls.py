"""PraxiApp URL Configuration.

API-Routen:
    /api/auth/         - Authentication (core)
    /api/health/       - Health check (core)
    /api/appointments/ - Termine (appointments)
    /api/operations/   - OPs (appointments)
    /api/patients/     - Patienten (patients)
"""

import os

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import FileResponse, HttpResponse
from django.shortcuts import render
from django.urls import include, path, re_path
from django.views.generic import RedirectView
from django.views.static import serve as static_serve
from praxi_backend.core.admin import praxi_admin_site
from praxi_backend.core.views import setup_database  # Temporary setup view


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


def favicon_view(request):
    """Serve favicon.ico - serves favicon.ico from static files"""
    from django.contrib.staticfiles.storage import staticfiles_storage

    # Try to serve favicon.ico from static files
    try:
        favicon_ico_path = staticfiles_storage.path("favicon.ico")
        if os.path.exists(favicon_ico_path):
            return FileResponse(open(favicon_ico_path, "rb"), content_type="image/x-icon")
    except Exception:
        pass

    # Fallback to favicon.svg if ICO doesn't exist
    try:
        favicon_svg_path = staticfiles_storage.path("favicon.svg")
        if os.path.exists(favicon_svg_path):
            return FileResponse(open(favicon_svg_path, "rb"), content_type="image/svg+xml")
    except Exception:
        pass

    # Final fallback: Return a simple 16x16 white square with blue cross (Medical Cross design)
    # This is a minimal valid ICO file with a simple design
    minimal_ico = (
        b"\x00\x00"  # Reserved
        b"\x01\x00"  # Type: ICO
        b"\x01\x00"  # Number of images
        b"\x10\x10"  # Width/Height: 16x16
        b"\x00\x00"  # Color palette: none
        b"\x01\x00"  # Reserved
        b"\x20\x00"  # Planes: 1
        b"\x00\x00\x00\x00"  # Bits per pixel: 32
        b"\x40\x01\x00\x00"  # Image data size: 320 bytes (16*16*4 + 40 header)
        b"\x16\x00\x00\x00"  # Offset: 22 bytes
        # BITMAPINFOHEADER (40 bytes)
        b"\x28\x00\x00\x00"  # Header size: 40
        b"\x10\x00\x00\x00"  # Width: 16
        b"\x20\x00\x00\x00"  # Height: 32 (16*2 for XOR and AND masks)
        b"\x01\x00"  # Planes: 1
        b"\x20\x00"  # Bits per pixel: 32
        b"\x00\x00\x00\x00"  # Compression: none
        b"\x00\x01\x00\x00"  # Image size: 256 bytes
        b"\x00\x00\x00\x00"  # X pixels per meter: 0
        b"\x00\x00\x00\x00"  # Y pixels per meter: 0
        b"\x00\x00\x00\x00"  # Colors used: 0
        b"\x00\x00\x00\x00"  # Important colors: 0
        # Pixel data: 16x16 RGBA (256 pixels = 1024 bytes)
        # White background with blue medical cross
        b"\xff\xff\xff\xff" * 64  # Top 4 rows (white)
        + b"\xff\xff\xff\xff" * 2
        + b"\xe2\x4a\x90\xff" * 4
        + b"\xff\xff\xff\xff" * 2
        + b"\xff\xff\xff\xff" * 2
        + b"\xe2\x4a\x90\xff" * 4
        + b"\xff\xff\xff\xff" * 2  # Row 5 (cross horizontal)
        + b"\xff\xff\xff\xff" * 2
        + b"\xe2\x4a\x90\xff" * 4
        + b"\xff\xff\xff\xff" * 2
        + b"\xff\xff\xff\xff" * 2
        + b"\xe2\x4a\x90\xff" * 4
        + b"\xff\xff\xff\xff" * 2  # Row 6
        + b"\xff\xff\xff\xff" * 2
        + b"\xe2\x4a\x90\xff" * 4
        + b"\xff\xff\xff\xff" * 2
        + b"\xff\xff\xff\xff" * 2
        + b"\xe2\x4a\x90\xff" * 4
        + b"\xff\xff\xff\xff" * 2  # Row 7
        + b"\xff\xff\xff\xff" * 2
        + b"\xe2\x4a\x90\xff" * 4
        + b"\xff\xff\xff\xff" * 2
        + b"\xff\xff\xff\xff" * 2
        + b"\xe2\x4a\x90\xff" * 4
        + b"\xff\xff\xff\xff" * 2  # Row 8
        + b"\xff\xff\xff\xff" * 2
        + b"\xe2\x4a\x90\xff" * 4
        + b"\xff\xff\xff\xff" * 2
        + b"\xff\xff\xff\xff" * 2
        + b"\xe2\x4a\x90\xff" * 4
        + b"\xff\xff\xff\xff" * 2  # Row 9
        + b"\xff\xff\xff\xff" * 2
        + b"\xe2\x4a\x90\xff" * 4
        + b"\xff\xff\xff\xff" * 2
        + b"\xff\xff\xff\xff" * 2
        + b"\xe2\x4a\x90\xff" * 4
        + b"\xff\xff\xff\xff" * 2  # Row 10
        + b"\xff\xff\xff\xff" * 2
        + b"\xe2\x4a\x90\xff" * 4
        + b"\xff\xff\xff\xff" * 2
        + b"\xff\xff\xff\xff" * 2
        + b"\xe2\x4a\x90\xff" * 4
        + b"\xff\xff\xff\xff" * 2  # Row 11
        + b"\xff\xff\xff\xff" * 2
        + b"\xe2\x4a\x90\xff" * 4
        + b"\xff\xff\xff\xff" * 2
        + b"\xff\xff\xff\xff" * 2
        + b"\xe2\x4a\x90\xff" * 4
        + b"\xff\xff\xff\xff" * 2  # Row 12
        + b"\xff\xff\xff\xff" * 64  # Bottom 4 rows (white)
        # AND mask: 16x16 monochrome (32 bytes) - all transparent
        + b"\x00\x00" * 16
    )
    return HttpResponse(minimal_ico, content_type="image/x-icon")


urlpatterns = [
    # Root & Admin
    path("", root, name="root"),
    path("favicon.ico", favicon_view, name="favicon"),  # Favicon handler
    # Temporary setup endpoint - DELETE AFTER FIRST USE!
    path("setup/", setup_database, name="setup_database"),
    path("admin/", admin.site.urls),  # Standard Django Admin
    path(
        "praxi_backend/dashboard/", include("praxi_backend.dashboard.urls")
    ),  # Dashboard (MUSS VOR praxi_backend/ stehen!)
    path(
        "praxi_backend/core/user/",
        RedirectView.as_view(
            url="/praxi_backend/Dashboardadministration/core/user/", permanent=False
        ),
    ),
    path(
        "praxi_backend/appointments/operation/",
        RedirectView.as_view(
            url="/praxi_backend/Dashboardadministration/appointments/operation/", permanent=False
        ),
    ),
    path("praxi_backend/Dashboardadministration/", praxi_admin_site.urls),  # Custom PraxiApp Admin
    path(
        "praxi_backend/",
        RedirectView.as_view(url="/praxi_backend/Dashboardadministration/", permanent=False),
    ),
    # API Routes - Order matters!
    path("api/", include("praxi_backend.core.urls")),
    path("api/", include("praxi_backend.appointments.urls")),
    path("api/", include("praxi_backend.patients.urls")),
]

# Static Files für Development
if settings.DEBUG:
    # WICHTIG: staticfiles_urlpatterns() MUSS zuerst kommen,
    # da es die Static Files aus STATICFILES_DIRS serviert
    from django.contrib.staticfiles.urls import staticfiles_urlpatterns

    urlpatterns += staticfiles_urlpatterns()
    # Zusätzlich STATIC_ROOT servieren (falls verwendet)
    if settings.STATIC_ROOT:
        urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Media uploads (DEBUG oder explizit per SERVE_MEDIA)
if getattr(settings, "DEBUG", False) and settings.MEDIA_ROOT:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Media uploads fuer lokale Tests auch bei DEBUG=False
if getattr(settings, "SERVE_MEDIA", False) and settings.MEDIA_ROOT:
    urlpatterns += [
        re_path(r"^media/(?P<path>.*)$", static_serve, {"document_root": settings.MEDIA_ROOT}),
    ]
