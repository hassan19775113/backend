from django.db import models


class Patient(models.Model):
    """Local patient cache for the system database.

    NOTE: This is NOT a ForeignKey to the medical DB.
    patient_id references the legacy medical.Patient but is stored as an integer.
    All writes go to the 'default' database.

    This table caches patient data from the legacy medical DB for:
    - Faster lookups
    - Offline access
    - Local modifications before sync
    """

    patient_id = models.IntegerField(unique=True, db_index=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    birth_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # WICHTIG: Andere Tabelle als medical.Patient!
        db_table = 'patients_cache'
        ordering = ['last_name', 'first_name', 'id']
        verbose_name = 'Patient (Cache)'
        verbose_name_plural = 'Patients (Cache)'

    def __str__(self) -> str:
        return f"{self.last_name}, {self.first_name} (patient_id={self.patient_id})"
