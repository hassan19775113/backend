"""Compatibility import package.

The real Django app package is `praxi_backend.appointments`.

This wrapper avoids any `sys.modules` aliasing (which can create duplicate
models under the wrong module path). It is only a light re-export.
"""

from __future__ import annotations

from praxi_backend.appointments.models import Appointment, Operation  # noqa: F401

__all__ = ["Appointment", "Operation"]
