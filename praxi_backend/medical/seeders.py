import random
from datetime import date, timedelta, datetime

from django.db import transaction

from .models import Patient

RANDOM_SEED = 42


def seed_medical() -> dict:
    """
    Seedet Patienten, ABER:
    - löscht NIE bestehende Daten
    - erzeugt nur neue Patienten, wenn Tabelle leer ist

    Das schützt echte Produktionsdaten, falls dieselbe DB genutzt wird.
    """
    random.seed(RANDOM_SEED)
    stats: dict[str, int] = {"medical_patients": 0}

    # Wenn bereits Patienten vorhanden sind, nicht anfassen
    if Patient.objects.exists():
        return stats

    with transaction.atomic():
        patients = _seed_patients()
        stats["medical_patients"] = len(patients)

    return stats


def _seed_patients() -> list[Patient]:
    first_names_male = ["Ali", "Omar", "Karim", "Hassan", "Yusuf", "Mahmoud"]
    first_names_female = ["Sara", "Layla", "Mariam", "Amina", "Noura", "Fatima"]
    last_names = ["Ahmad", "Salim", "Jabari", "Haddad", "Khalil", "Rahman", "Hamidi", "Faruq"]

    genders = ["male", "female", "other"]
    patients: list[Patient] = []

    base_date = date.today()

    for i in range(20):
        if random.random() < 0.5:
            first_name = random.choice(first_names_male)
            gender = "male"
        else:
            first_name = random.choice(first_names_female)
            gender = "female"

        last_name = random.choice(last_names)
        birth_year = random.randint(1940, 2010)
        birth_month = random.randint(1, 12)
        birth_day = random.randint(1, 28)
        birth_date = date(birth_year, birth_month, birth_day)

        phone = f"+49 170 {random.randint(1000000, 9999999)}"
        email = f"{first_name.lower()}.{last_name.lower()}@example.com"

        created_at = datetime.combine(base_date - timedelta(days=random.randint(0, 365)), datetime.min.time())
        updated_at = created_at + timedelta(days=random.randint(0, 60))

        patient = Patient.objects.create(
            first_name=first_name,
            last_name=last_name,
            birth_date=birth_date,
            gender=gender,
            phone=phone,
            email=email,
            created_at=created_at,
            updated_at=updated_at,
        )
        patients.append(patient)

    return patients