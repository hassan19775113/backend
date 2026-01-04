"""Database router for PraxiApp (dual-database architecture).

PraxiApp uses two database aliases:

- ``default``: Django-managed system database (auth, sessions, admin) AND all managed
    application data (core, appointments, patients, dashboard).
- ``medical``: Legacy medical database that contains patient master data. This database
    is treated as *read-only* from the Django application's perspective and must never
    be migrated by Django.

This router enforces:

- Reads/Writes for the ``medical`` app go to the ``medical`` alias.
- All other apps go to ``default``.
- Migrations are allowed **only** on ``default`` and **never** for the ``medical`` app.

Why this exists (medical domain rationale):

- Patient data is typically owned by a legacy practice system.
- PraxiApp references patients by integer ``patient_id`` in managed tables to avoid
    cross-database foreign keys.
"""


class PraxiAppRouter:

    """DB router implementing the split between system DB and legacy medical DB."""

    system_app_labels = {
        'admin',
        'auth',
        'contenttypes',
        'sessions',
        'messages',
        'staticfiles',
        'core',
        'appointments',
        'patients',
    }

    medical_app_labels = {
        'medical',
    }

    def db_for_read(self, model, **hints):
        """Route read queries to the correct database alias."""
        if model._meta.app_label in self.medical_app_labels:
            return 'medical'

        return 'default'

    def db_for_write(self, model, **hints):
        """Route write queries to the correct database alias.

        Note: In production, the ``medical`` database is intended to be read-only.
        The router still returns ``medical`` for writes to ``medical`` models to
        avoid accidental writes to ``default`` for unmanaged legacy models.
        """
        if model._meta.app_label in self.medical_app_labels:
            return 'medical'

        return 'default'

    def allow_relation(self, obj1, obj2, **hints):
        """Allow relations only within the same database.

        Cross-DB relations are intentionally blocked because they are not enforceable
        at the database level and can break referential integrity.
        """
        # Relationen nur innerhalb derselben DB sinnvoll.
        if obj1._state.db and obj2._state.db:
            return obj1._state.db == obj2._state.db
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """Control which apps may run migrations on which database."""
        # Nie Migrationen für die medical App (weder auf default noch medical).
        if app_label in self.medical_app_labels:
            return False

        # Niemals Migrationen auf der medizinischen DB.
        if db == 'medical':
            return False

        # Auf der System-DB nur System-Apps + core.
        if db == 'default':
            return app_label in self.system_app_labels

        return None
