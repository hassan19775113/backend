# Migrationsplan (noch NICHT ausführen)

Ziel: Django nutzt **zwei PostgreSQL-Datenbanken**

- `default` = System-DB (Django Auth/Rollen/Admin/Sessions + `core`)
- `medical` = bestehende medizinische Bestands-DB (PraxiApp-Schema), **keine Django-Migrationen**

## 0) Voraussetzungen

1) System-DB existiert (Default-Name ist `praxiapp_system`, anpassbar über `SYS_DB_NAME`).
2) Zugangsdaten/Host/Port sind korrekt gesetzt.

Empfohlene ENV Vars (Beispiele):

- System-DB:
  - `SYS_DB_NAME=praxiapp_system`
  - `SYS_DB_USER=postgres`
  - `SYS_DB_PASSWORD=`
  - `SYS_DB_HOST=localhost`
  - `SYS_DB_PORT=5432`

- Medical-DB:
  - `MED_DB_NAME=praxiapp`
  - `MED_DB_USER=postgres`
  - `MED_DB_PASSWORD=`
  - `MED_DB_HOST=localhost`
  - `MED_DB_PORT=5432`

## 1) Vorab-Check (read-only)

- `python manage.py check`
- Optional: `python manage.py shell -c "from django.db import connections; connections['default'].cursor().execute('SELECT 1'); print('ok')"`

## 2) Migrationen (nur System-DB)

WICHTIG: Migrationen werden **nur** auf `default` angewendet.

- `python manage.py migrate --database=default`

Falls die System-DB noch nicht existiert:
- DB einmalig anlegen (z.B. via `createdb praxiapp_system` oder über pgAdmin), dann erst migrieren.

Erwartung:
- Django legt/aktualisiert nur Systemtabellen + `core_*` Tabellen in der System-DB.
- Auf `medical` darf *nichts* migriert werden.

## 3) Superuser (nur System-DB)

- `python manage.py createsuperuser`

## 4) Rollen seed (optional, später)

- Minimal: Roles `doctor`, `assistant`, `admin`, `billing` in `core_role` anlegen.

## 5) Medical-Models (später)

- Medical Tabellen per `managed = False` anbinden.
- Router erweitern: Reads/Writes für medical Apps auf `medical` routen.
- Keine Migrationen für diese Modelle.
