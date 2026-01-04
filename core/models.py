"""Compatibility wrapper for `praxi_backend.core.models`.

Do NOT alias module objects in `sys.modules` here. We only re-export symbols so
imports like `from core.models import User` don't create duplicate Django model
classes under a different module path.
"""

from __future__ import annotations

from praxi_backend.core.models import *  # noqa: F403

