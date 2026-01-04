"""Compatibility wrapper for `praxi_backend.appointments.serializers`.

Tests in this repository should patch `praxi_backend.appointments.serializers.*`
to ensure patches apply to the real implementation.
"""

from __future__ import annotations

from praxi_backend.appointments.serializers import *  # noqa: F403

