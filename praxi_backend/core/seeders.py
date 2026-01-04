import random
from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.db import transaction

from .models import Role, AuditLog

User = get_user_model()

RANDOM_SEED = 42


def seed_core(flush: bool = False) -> dict:
    """
    Seedet:
    - Rollen
    - Benutzer
    - AuditLog-Einträge

    Wenn flush=True:
        - Löscht AuditLogs
        - Löscht NICHT Superuser
        - Löscht nur Benutzer, deren E-Mail auf '@seed.local' endet
    """
    random.seed(RANDOM_SEED)

    stats: dict[str, int] = {}

    with transaction.atomic():
        if flush:
            AuditLog.objects.all().delete()
            User.objects.filter(is_superuser=False, email__endswith="@seed.local").delete()
            Role.objects.all().delete()

        roles = _seed_roles()
        stats["core_roles"] = len(roles)

        users = _seed_users(roles)
        stats["core_users"] = len(users)

        logs = _seed_audit_logs(users)
        stats["core_audit_logs"] = logs

    return stats


def _seed_roles() -> list[Role]:
    role_definitions = [
        ("admin", "Admin"),
        ("assistant", "Assistent"),
        ("doctor", "Arzt"),
        ("billing", "Abrechnung"),
        ("nurse", "Pflege"),
        ("reception", "Empfang"),
        ("lab", "Labor"),
        ("management", "Management"),
    ]

    roles: list[Role] = []
    for name, label in role_definitions:
        role, _created = Role.objects.get_or_create(name=name, defaults={"label": label})
        roles.append(role)
    return roles
    return roles


def _seed_users(roles: list[Role]) -> list[User]:
    users: list[User] = []

    def get_role(name: str) -> Role | None:
        return next((r for r in roles if r.name == name), None)

    # 1. Superuser (falls noch nicht vorhanden)
    if not User.objects.filter(is_superuser=True).exists():
        su = User.objects.create_superuser(
            username="admin",
            email="admin@praxi.local",
            password="admin",
        )
        su.role = get_role("admin")
        su.calendar_color = "#1E90FF"
        su.save()
        users.append(su)

    # 2. Ärzte
    doctor_role = get_role("doctor")
    doctor_names = [
        ("dr.mueller", "Anna", "Müller"),
        ("dr.schmidt", "Thomas", "Schmidt"),
        ("dr.meier", "Julia", "Meier"),
        ("dr.lehmann", "David", "Lehmann"),
        ("dr.klein", "Sarah", "Klein"),
    ]
    for username, first_name, last_name in doctor_names:
        if User.objects.filter(username=username).exists():
            user = User.objects.get(username=username)
        else:
            user = User.objects.create_user(
                username=username,
                email=f"{username}@seed.local",
                password="test1234",
                first_name=first_name,
                last_name=last_name,
            )
        user.role = doctor_role
        user.calendar_color = random.choice(["#1E90FF", "#32CD32", "#FF8C00", "#8A2BE2"])
        user.is_staff = True
        user.save()
        users.append(user)

    # 3. Pflege
    nurse_role = get_role("nurse")
    nurse_names = [
        ("pflege1", "Lisa", "Walter"),
        ("pflege2", "Markus", "Becker"),
        ("pflege3", "Nina", "Schuster"),
    ]
    for username, first_name, last_name in nurse_names:
        if User.objects.filter(username=username).exists():
            user = User.objects.get(username=username)
        else:
            user = User.objects.create_user(
                username=username,
                email=f"{username}@seed.local",
                password="test1234",
                first_name=first_name,
                last_name=last_name,
            )
        user.role = nurse_role
        user.calendar_color = "#20B2AA"
        user.is_staff = True
        user.save()
        users.append(user)

    # 4. Empfang
    reception_role = get_role("reception")
    reception_names = [
        ("empfang1", "Sophie", "Hartmann"),
        ("empfang2", "Jonas", "Krüger"),
    ]
    for username, first_name, last_name in reception_names:
        if User.objects.filter(username=username).exists():
            user = User.objects.get(username=username)
        else:
            user = User.objects.create_user(
                username=username,
                email=f"{username}@seed.local",
                password="test1234",
                first_name=first_name,
                last_name=last_name,
            )
        user.role = reception_role
        user.calendar_color = "#FF69B4"
        user.is_staff = True
        user.save()
        users.append(user)

    # 5. Labor / Management (je 1)
    for username, first_name, last_name, role_name in [
        ("labor1", "Felix", "Maier", "lab"),
        ("manager1", "Klara", "Vogel", "management"),
    ]:
        if User.objects.filter(username=username).exists():
            user = User.objects.get(username=username)
        else:
            user = User.objects.create_user(
                username=username,
                email=f"{username}@seed.local",
                password="test1234",
                first_name=first_name,
                last_name=last_name,
            )
        user.role = get_role(role_name)
        user.calendar_color = "#708090"
        user.is_staff = True
        user.save()
        users.append(user)

    return users


def _seed_audit_logs(users: list[User]) -> int:
    if not users:
        return 0

    actions = [
        "CREATE_APPOINTMENT",
        "UPDATE_APPOINTMENT",
        "CANCEL_APPOINTMENT",
        "CREATE_OPERATION",
        "UPDATE_OPERATION",
        "VIEW_PATIENT",
    ]

    # Wir erzeugen bewusst eine kleinere Menge (z.B. 50 Logs)
    count = 0
    now = datetime.now()

    for i in range(50):
        user = random.choice(users)
        role_name = user.role.label if user.role else "Unbekannt"
        action = random.choice(actions)
        patient_id = random.randint(1, 50)  # passt ungefähr zu unseren späteren Patienten-Seeds
        timestamp = now - timedelta(minutes=random.randint(0, 60 * 24 * 7))  # letzte 7 Tage

        AuditLog.objects.create(
            user=user,
            role_name=role_name,
            action=action,
            patient_id=patient_id,
            timestamp=timestamp,
            meta={
                "source": "seed",
                "info": f"Dummy Audit-Eintrag {i + 1}",
            },
        )
        count += 1

    return count