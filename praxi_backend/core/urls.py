"""Core App URLs - Authentication & Health.

Prefix: /api/
Routes:
    GET  /api/health/       - Health check (no auth)
    POST /api/auth/login/   - JWT token obtain with user/role info
    POST /api/auth/refresh/ - JWT token refresh
    GET  /api/auth/me/      - Current user info (requires auth)
"""

from django.urls import path

from praxi_backend.core.views import (
    health,
    LoginView,
    MeView,
    RefreshView,
)

app_name = 'core'

urlpatterns = [
    # Health check
    path('health/', health, name='health'),

    # JWT Authentication
    path('auth/login/', LoginView.as_view(), name='login'),
    path('auth/refresh/', RefreshView.as_view(), name='refresh'),
    path('auth/me/', MeView.as_view(), name='me'),
]
