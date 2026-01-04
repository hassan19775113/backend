"""Compatibility shim for Django/unittest discovery.

The project stores real tests under `praxi_backend/core/tests/` but also keeps
the `tests.py` module (created by `startapp`).

To allow discovery/imports like `praxi_backend.core.tests.test_auth`, we expose
`tests/` as a submodule search location while keeping the app directory as the
first `__path__` entry (required by newer unittest discovery).
"""

from __future__ import annotations

import os as _os

_here = _os.path.dirname(__file__)
__path__ = [_here, _os.path.join(_here, "tests")]
