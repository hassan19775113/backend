"""Compatibility import package.

Historically this repo used short imports like `from core.models import User`.
The real Django app package is `praxi_backend.core`.

This wrapper intentionally does *not* alias module names in `sys.modules`
(which can lead to Django registering duplicate models under the wrong module
path). It simply re-exports symbols for convenience.
"""

from __future__ import annotations

# Re-export common names (kept minimal on purpose).
from praxi_backend.core.models import Role, User, AuditLog  # noqa: F401

__all__ = ["User", "Role", "AuditLog"]
