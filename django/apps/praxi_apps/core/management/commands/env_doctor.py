from __future__ import annotations

import json
import sys
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError


def _ensure_repo_root_on_syspath() -> None:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if parent.name == "django":
            repo_root = parent.parent
            if str(repo_root) not in sys.path:
                sys.path.insert(0, str(repo_root))
            return


_ensure_repo_root_on_syspath()

from scripts.agents.env_doctor import format_human, run_env_doctor  # noqa: E402


class Command(BaseCommand):
    help = "Validate runtime environment and Django/PostgreSQL readiness for CI"

    def add_arguments(self, parser):
        parser.add_argument(
            "--json",
            action="store_true",
            help="Emit machine-readable JSON output.",
        )

    def handle(self, *args, **options):
        as_json = options.get("json", False)

        payload = run_env_doctor()

        if as_json:
            self.stdout.write(json.dumps(payload, indent=2))
        else:
            self.stdout.write(format_human(payload))

        if payload.get("errors"):
            raise CommandError("env_doctor detected blocking issues")
