"""Compatibility shim for Django/unittest discovery.

This project keeps both:
- `praxi_backend/appointments/tests.py` (created by `startapp`)
- `praxi_backend/appointments/tests/` (actual test modules)

Python's import system cannot normally treat a module (tests.py) as a package.
Historically we set `__path__` to the `tests/` directory to allow importing
submodules like `praxi_backend.appointments.tests.test_conflicts`.

With newer Python/unittest discovery this can raise:

	ImportError: 'tests' module incorrectly imported from '.../appointments/tests'.
	Expected '.../appointments'.

The fix is to make the *first* entry in `__path__` match the directory that
unittest expects (the app directory), while still including the `tests/`
directory so submodules are importable.
"""

from __future__ import annotations

import os as _os

_here = _os.path.dirname(__file__)

# First element must be the app directory (expected by unittest), while the
# `tests/` directory enables importing the actual test modules.
__path__ = [_here, _os.path.join(_here, "tests")]
