from __future__ import annotations

import importlib

from django.conf import settings
from django.test.runner import DiscoverRunner
from django.test.utils import override_settings, setup_databases, teardown_databases


class PraxiAppTestRunner(DiscoverRunner):
    """PraxiApp test runner.

    Single-database architecture:
    - Django creates a test DB only for alias "default".
    - No multi-DB routing / no secondary DB aliases.
    """

    _test_flags_override = None

    def setup_test_environment(self, **kwargs):
        super().setup_test_environment(**kwargs)
        self._test_flags_override = override_settings(PRAXI_RUNNING_TESTS=True)
        self._test_flags_override.enable()

    def teardown_test_environment(self, **kwargs):
        if self._test_flags_override is not None:
            self._test_flags_override.disable()
            self._test_flags_override = None
        super().teardown_test_environment(**kwargs)

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
        # On Python 3.14+, `unittest` discovery from a filesystem directory can raise
        # ImportError in repos that have `tests/` directories under app packages.
        #
        # Users often run `manage.py test praxi_backend` which passes a package label
        # and triggers filesystem discovery. Normalize that to dotted module labels.
        if test_labels:
            # Treat `praxi_backend` as "run all app tests".
            if any(label == "praxi_backend" for label in test_labels):
                test_labels = None
            else:
                normalized: list[str] = []
                for label in test_labels:
                    if label.startswith("praxi_backend.") and not label.endswith(".tests"):
                        candidate = f"{label}.tests"
                        try:
                            importlib.import_module(candidate)
                        except Exception:
                            normalized.append(label)
                        else:
                            normalized.append(candidate)
                    else:
                        normalized.append(label)
                test_labels = normalized

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
