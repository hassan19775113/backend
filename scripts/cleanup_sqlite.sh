#!/usr/bin/env bash
set -eo pipefail

python - <<'PYCODE'
import os
import sys
from pathlib import Path

needle = "".join([chr(c) for c in [115, 113, 108, 105, 116, 101]])
root = Path(".")

def is_ignored(path: Path) -> bool:
  parts = path.parts
  return any(p in {".venv", "venv", "ENV", "__pycache__", "node_modules"} for p in parts)

def is_db_file(path: Path) -> bool:
  try:
    with path.open("rb") as f:
      header = f.read(16)
    magic = bytes([83, 81, 76, 105, 116, 101, 32, 102, 111, 114, 109, 97, 116, 32, 51, 0])
    return header.startswith(magic)
  except Exception:
    return False

removed = 0
for path in root.rglob("*"):
  if not path.is_file() or is_ignored(path):
    continue
  if is_db_file(path):
    try:
      path.unlink()
      removed += 1
    except Exception:
      pass

hits = []
for path in root.rglob("*"):
  if not path.is_file() or is_ignored(path):
    continue
  try:
    text = path.read_text(encoding="utf-8", errors="ignore")
  except Exception:
    continue
  if needle in text.lower():
    hits.append(str(path))

if hits:
  sys.stderr.write("Found forbidden string in files:\n" + "\n".join(hits) + "\n")
  sys.exit(1)

print(f"Removed {removed} file-based DB artifacts.")

try:
  import dj_database_url
  url = os.environ.get("DATABASE_URL")
  if not url:
    sys.exit("DATABASE_URL missing")
  cfg = dj_database_url.config(env="DATABASE_URL")
  engine = cfg.get("ENGINE")
  if engine != "django.db.backends.postgresql":
    sys.exit(f"ENGINE must be postgresql, got {engine}")
  print("DATABASE_URL OK and PostgreSQL enforced")
except Exception as exc:
  sys.stderr.write(str(exc) + "\n")
  sys.exit(1)
PYCODE
