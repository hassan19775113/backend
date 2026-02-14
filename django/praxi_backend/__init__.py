from __future__ import annotations

from pathlib import Path

# Phase 7: folder reorg
# Keep import paths stable (e.g. `praxi_backend.core`) while allowing the app
# packages to live under: <BASE_DIR>/apps/praxi_apps/<app>
try:
    _apps_pkg = Path(__file__).resolve().parent.parent / "apps" / "praxi_apps"
    if _apps_pkg.exists():
        __path__.append(str(_apps_pkg))
except Exception:
    # Best-effort only; never break imports if filesystem is in an unexpected state.
    pass

# Celery is not available in Vercel serverless environment
# Only import if celery is installed (for local development)
try:
    from .celery import app as celery_app
    __all__ = ("celery_app",)
except ImportError:
    # Running in Vercel or environment without Celery
    __all__ = ()

