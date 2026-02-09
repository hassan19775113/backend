# PostgreSQL-only checklist

- Install and start PostgreSQL locally (default port 5432).
- Set DATABASE_URL before running Django:
  - Windows PowerShell: `$env:DATABASE_URL = "postgresql://USER:PASSWORD@HOST:5432/DBNAME"`
  - macOS/Linux: `export DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DBNAME`
- Verify DATABASE_URL uses PostgreSQL:
  - `python - <<'PY'
import os, dj_database_url
cfg = dj_database_url.config(env="DATABASE_URL")
assert cfg["ENGINE"] == "django.db.backends.postgresql"
print("PostgreSQL confirmed")
PY`
- Run migrations:
  - `python django/manage.py migrate`
- Create a superuser if needed:
  - `python django/manage.py createsuperuser`
- Load local fixtures (optional):
  - `python django/manage.py loaddata path/to/fixture.json`
- Confirm runtime DB engine:
  - `python django/manage.py shell -c "from django.conf import settings; print(settings.DATABASES['default']['ENGINE'])"`
- Ensure no local file-based DB artifacts exist:
  - `Get-ChildItem -Recurse -File | ForEach-Object { $h = [IO.File]::OpenRead($_.FullName); $b = New-Object byte[] 16; $h.Read($b,0,16) | Out-Null; $h.Dispose(); $magic = [byte[]](83,81,76,105,116,101,32,102,111,114,109,97,116,32,51,0); if ($b[0..15] -ceq $magic) { $_.FullName } }`
