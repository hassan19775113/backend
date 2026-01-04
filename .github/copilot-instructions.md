# PraxiApp Backend - AI Coding Instructions

## Architecture Overview

PraxiApp is a **Django REST API** for medical practice management with a **dual-database architecture**:

- **`default`** (PostgreSQL: `praxiapp_system`) – Django system data (auth, sessions) + managed app data (`core`, `appointments`)
- **`medical`** (PostgreSQL: `praxiapp`) – Read-only legacy medical database (patients). **Never migrated by Django**.

The `PraxiAppRouter` in [db_router.py](../praxi_backend/db_router.py) enforces this split. Models in `medical` app use `managed = False`.

### App Structure
Apps live under `praxi_backend/` (not project root):
- **`core`** – Custom `User` model, `Role`, `AuditLog`, JWT auth endpoints
- **`appointments`** – Appointments, Operations, Resources, Scheduling, Patient Flow
- **`medical`** – Unmanaged models (`Patient`) for legacy DB

## Key Patterns

### RBAC Permissions
Roles: `admin`, `assistant`, `doctor`, `billing`. Each endpoint uses a dedicated permission class:
```python
# praxi_backend/appointments/permissions.py
class AppointmentPermission(BasePermission):
    read_roles = {"admin", "assistant", "doctor", "billing"}
    write_roles = {"admin", "assistant", "doctor"}
    # doctor role is further filtered to own records in has_object_permission
```
Follow this pattern: define `read_roles`/`write_roles` sets, implement `has_permission` + `has_object_permission`.

### Audit Logging
All patient-related actions must be logged via `log_patient_action()`:
```python
from praxi_backend.core.utils import log_patient_action
log_patient_action(request.user, 'appointment_create', patient_id=obj.patient_id)
```

### Cross-DB Patient References
Patient data lives in the medical DB. Store only `patient_id` (integer) in managed models:
```python
patient_id = models.IntegerField()  # NOT a ForeignKey
```

### Serializers
- Use explicit `using('default')` for querysets in serializers when referencing User/Role
- Separate `CreateUpdateSerializer` and read `Serializer` classes for complex models

## Database Commands

```powershell
# Activate venv first
& .\.venv\Scripts\Activate.ps1

# Migrations apply ONLY to 'default' database
python manage.py migrate --database=default

# Create superuser (system DB)
python manage.py createsuperuser
```

## Testing

Uses custom `PraxiAppTestRunner` – creates test DB only for `default`, leaves `medical` untouched.

```powershell
# Run all tests
python manage.py test praxi_backend

# Run specific test module
python manage.py test praxi_backend.appointments.tests.test_appointment_suggest
```

### Test Conventions
- Set `databases = {"default"}` on test classes
- Use `User.objects.db_manager("default").create_user(...)` for user creation
- Use `.using("default")` on all ORM calls within tests
- Create roles inline: `Role.objects.using("default").get_or_create(name="admin", ...)`

Example pattern from [test_operations_rbac.py](../praxi_backend/appointments/tests/test_operations_rbac.py):
```python
class MyTest(TestCase):
    databases = {"default"}
    
    def setUp(self):
        role_admin, _ = Role.objects.using("default").get_or_create(name="admin", ...)
        self.admin = User.objects.db_manager("default").create_user(username="...", role=role_admin)
```

## API Endpoints

Base path: `/api/` (via `praxi_backend/core/urls.py` and `praxi_backend/appointments/urls.py`)

Key endpoints:
- Auth: `/api/auth/login/`, `/api/auth/refresh/`, `/api/auth/me/`
- Appointments: `/api/appointments/`, `/api/appointments/suggest/`
- Operations: `/api/operations/`, `/api/op-dashboard/`, `/api/op-timeline/`
- Calendar: `/api/calendar/day/`, `/api/calendar/week/`, `/api/calendar/month/`
- Scheduling: `/api/practice-hours/`, `/api/doctor-hours/`, `/api/doctor-absences/`

## Scheduling Logic

Appointment/operation suggestions in [scheduling.py](../praxi_backend/appointments/scheduling.py):
- Respects `PracticeHours`, `DoctorHours`, `DoctorAbsence`, `DoctorBreak`
- `weekday` field: 0=Monday, 6=Sunday
- Resources can be `room` or `device` types

## Seeders

Data seeding via app-specific seeders:
```python
from praxi_backend.core.seeders import seed_core
from praxi_backend.appointments.seeders import seed_appointments
```
Seeders use `random.seed(42)` for deterministic test data.

---

## Environment Setup (.env)

Create a `.env` file in the project root with the following structure:

```env
# System-DB (Django-managed, read/write)
SYS_DB_NAME=praxiapp_system
SYS_DB_USER=postgres
SYS_DB_PASSWORD=your_password
SYS_DB_HOST=localhost
SYS_DB_PORT=5432

# Medical-DB (Legacy, read-only – NEVER migrated)
MED_DB_NAME=praxiapp
MED_DB_USER=postgres
MED_DB_PASSWORD=your_password
MED_DB_HOST=localhost
MED_DB_PORT=5432

# Optional
DJANGO_SECRET_KEY=your-secret-key
JWT_SIGNING_KEY=your-jwt-key
REDIS_HOST=localhost
```

**Critical distinction:**
| Variable Prefix | Database Alias | Purpose | Access |
|-----------------|----------------|---------|--------|
| `SYS_DB_*` | `default` | Django system + managed models | Read/Write |
| `MED_DB_*` | `medical` | Legacy patient data | **Read-only** |

⚠️ **Migrations run ONLY on `default` database.** Never run `migrate --database=medical`.

---

## Import Conventions

**Production code** uses fully qualified imports:
```python
from praxi_backend.core.models import User, Role, AuditLog
from praxi_backend.appointments.models import Appointment, Operation
from praxi_backend.medical.models import Patient
```

**Test code** uses short imports (Django test discovery adds apps to path):
```python
from core.models import User, Role, AuditLog
from appointments.models import Appointment, Operation
```

**Rule for Copilot:** Always use fully qualified `praxi_backend.<app>.*` imports in production code. Short imports are only acceptable in test files under `tests/` directories.

---

## Celery / Redis

Celery is configured in [celery.py](../praxi_backend/celery.py) with Redis as broker:
```python
CELERY_BROKER_URL = f"redis://{os.environ.get('REDIS_HOST')}:6379/0"
```

**Current state:** No active Celery tasks exist. Background processing is not yet implemented.

**Rule for Copilot:** Do NOT generate Celery tasks unless explicitly requested. If async processing is needed, confirm with the user first.

---

## Development Patterns

### Creating a New Endpoint

1. **Model** (if needed) – see "Creating a New Model" below

2. **Serializer** in `praxi_backend/<app>/serializers.py`:
```python
class MyModelSerializer(serializers.ModelSerializer):
    # For User/Role references, use explicit DB routing:
    doctor = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.using('default').all()
    )
    
    class Meta:
        model = MyModel
        fields = ['id', 'doctor', 'patient_id', ...]

# Separate serializer for create/update if validation differs
class MyModelCreateUpdateSerializer(serializers.ModelSerializer):
    ...
```

3. **Permission** in `praxi_backend/<app>/permissions.py`:
```python
class MyModelPermission(BasePermission):
    read_roles = {"admin", "assistant", "doctor", "billing"}
    write_roles = {"admin", "assistant"}

    def _role_name(self, request):
        user = getattr(request, "user", None)
        role = getattr(user, "role", None)
        return getattr(role, "name", None)

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False
        role_name = self._role_name(request)
        if request.method in SAFE_METHODS:
            return role_name in self.read_roles
        return role_name in self.write_roles

    def has_object_permission(self, request, view, obj):
        role_name = self._role_name(request)
        if role_name == "doctor":
            # Doctors only access own records
            return getattr(obj, "doctor_id", None) == request.user.id
        return True
```

4. **View** in `praxi_backend/<app>/views.py`:
```python
class MyModelListCreateView(generics.ListCreateAPIView):
    permission_classes = [MyModelPermission]
    
    def get_queryset(self):
        return MyModel.objects.using('default').all()
    
    def get_serializer_class(self):
        if self.request.method in ['POST', 'PUT', 'PATCH']:
            return MyModelCreateUpdateSerializer
        return MyModelSerializer
    
    def perform_create(self, serializer):
        obj = serializer.save()
        log_patient_action(self.request.user, 'mymodel_create', patient_id=obj.patient_id)
```

5. **URL** in `praxi_backend/<app>/urls.py`:
```python
path('my-models/', MyModelListCreateView.as_view(), name='my_models_list'),
path('my-models/<int:pk>/', MyModelDetailView.as_view(), name='my_models_detail'),
```

### Creating a New Model

```python
from django.conf import settings
from django.db import models

class MyModel(models.Model):
    # ❌ NEVER: patient = ForeignKey(Patient, ...)  # Cross-DB FK not allowed
    # ✅ ALWAYS: Store patient_id as integer
    patient_id = models.IntegerField()
    
    # ForeignKey to User is OK (same DB)
    doctor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='my_models',
    )
    
    # Standard fields
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at', '-id']
```

After creating the model:
```powershell
python manage.py makemigrations <app_name>
python manage.py migrate --database=default
```

### Creating a New Permission Class

Follow the `read_roles` / `write_roles` pattern:

```python
from rest_framework.permissions import BasePermission, SAFE_METHODS

class MyPermission(BasePermission):
    """
    - admin: full access
    - assistant: full access  
    - doctor: read + write own records only
    - billing: read-only
    """
    read_roles = {"admin", "assistant", "doctor", "billing"}
    write_roles = {"admin", "assistant", "doctor"}

    def _role_name(self, request):
        user = getattr(request, "user", None)
        role = getattr(user, "role", None)
        return getattr(role, "name", None)

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False
        role_name = self._role_name(request)
        if not role_name:
            return False
        if request.method in SAFE_METHODS:
            return role_name in self.read_roles
        return role_name in self.write_roles

    def has_object_permission(self, request, view, obj):
        role_name = self._role_name(request)
        if role_name == "billing" and request.method not in SAFE_METHODS:
            return False
        if role_name == "doctor":
            return getattr(obj, "doctor_id", None) == getattr(request.user, "id", None)
        return True
```
