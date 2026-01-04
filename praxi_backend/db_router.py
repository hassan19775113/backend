class PraxiAppRouter:
    """DB-Router für PraxiApp.

    Ziel:
    - Django-Systemdaten (auth/admin/sessions/...) + core liegen in der System-DB (alias: default)
    - medizinische Bestands-DB (alias: medical) wird niemals von Django migriert
    """

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
        if model._meta.app_label in self.medical_app_labels:
            return 'medical'

        return 'default'

    def db_for_write(self, model, **hints):
        if model._meta.app_label in self.medical_app_labels:
            return 'medical'

        return 'default'

    def allow_relation(self, obj1, obj2, **hints):
        # Relationen nur innerhalb derselben DB sinnvoll.
        if obj1._state.db and obj2._state.db:
            return obj1._state.db == obj2._state.db
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
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
