from __future__ import annotations

import os
import importlib

from django.conf import settings
from django.test.runner import DiscoverRunner
from django.test.utils import setup_databases, teardown_databases


class PraxiAppTestRunner(DiscoverRunner):
	"""Test-Runner mit Multi-DB-Sonderregel.

	Ziel:
	- Django erstellt eine Test-DB nur für alias "default".
	- alias "medical" bleibt auf der echten Bestands-DB (read-only im Test).

	Wichtig:
	- Tests, die "medical" verwenden, dürfen NICHT schreiben.
	- Keine Flush/Migrations auf "medical".
	"""

	def build_suite(self, test_labels=None, **kwargs):
		"""Build the test suite.

		On Python 3.14+, `unittest` discovery from a filesystem directory can raise
		an ImportError in repos that have `tests/` directories under app packages
		(e.g. `praxi_backend/appointments/tests/`).

		To keep `python manage.py test` stable across Python versions, default to
		loading tests via dotted module paths (`<app>.tests`) instead of filesystem
		discovery. Each `<app>.tests` module/package provides `load_tests()` to load
		its `test_*.py` submodules.
		"""
		if not test_labels:
			labels: list[str] = []
			for app in settings.INSTALLED_APPS:
				if not app.startswith("praxi_backend."):
					continue
				candidate = f"{app}.tests"
				try:
					importlib.import_module(candidate)
				except Exception:
					continue
				labels.append(candidate)

			# Fallback: if nothing was importable, keep Django's default behavior.
			test_labels = labels or None

		return super().build_suite(test_labels, **kwargs)

	def setup_databases(self, **kwargs):
		aliases = ["default"]
		serialized_aliases = kwargs.get("serialized_aliases") or []
		serialized_aliases = [alias for alias in serialized_aliases if alias in aliases]

		return setup_databases(
			verbosity=self.verbosity,
			interactive=self.interactive,
			keepdb=self.keepdb,
			debug_sql=self.debug_sql,
			parallel=self.parallel,
			aliases=aliases,
			serialized_aliases=serialized_aliases,
		)

	def teardown_databases(self, old_config, **kwargs):
		return teardown_databases(
			old_config,
			verbosity=self.verbosity,
			parallel=self.parallel,
			keepdb=self.keepdb,
		)
