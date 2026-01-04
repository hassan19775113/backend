"""Compatibility wrapper for `praxi_backend.appointments.views`.

Tests in this repository should patch `praxi_backend.appointments.views.*` to
ensure patches apply to the real implementation.
"""

from __future__ import annotations

from praxi_backend.appointments.views import *  # noqa: F403

