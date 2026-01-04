"""Legacy medical database models (read-only).

Important:
- Models in this app are **unmanaged** (``managed = False``) and represent tables
    owned by an external/legacy practice system.
- In production, ORM access is routed to the ``medical`` database alias.
- Django must never create migrations for these tables.
"""

from django.db import models


class Patient(models.Model):
    """Patient master record from the legacy medical database.

    This model is intentionally minimal and read-only from the perspective of
    PraxiApp. Managed application tables reference patients via integer
    ``patient_id`` to avoid cross-database foreign keys.
    """
    id = models.AutoField(primary_key=True)

    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    birth_date = models.DateField()
    gender = models.CharField(max_length=20, null=True, blank=True)

    phone = models.CharField(max_length=50, null=True, blank=True)
    email = models.CharField(max_length=255, null=True, blank=True)

    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'patients'

    def __str__(self) -> str:
        return f"{self.last_name}, {self.first_name}"
