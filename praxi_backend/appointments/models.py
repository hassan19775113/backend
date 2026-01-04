from django.conf import settings
from django.db import models


class AppointmentType(models.Model):
	name = models.CharField(max_length=100)
	color = models.CharField(max_length=7, blank=True, null=True, default="#2E8B57")
	duration_minutes = models.IntegerField(blank=True, null=True)
	active = models.BooleanField(default=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ["name", "id"]

	def __str__(self) -> str:
		return self.name


class PracticeHours(models.Model):
	weekday = models.IntegerField()  # 0=Monday ... 6=Sunday
	start_time = models.TimeField()
	end_time = models.TimeField()
	active = models.BooleanField(default=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ["weekday", "start_time", "id"]

	def __str__(self) -> str:
		return f"PracticeHours weekday={self.weekday} {self.start_time}-{self.end_time}"


class DoctorHours(models.Model):
	doctor = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name='doctor_hours',
	)
	weekday = models.IntegerField()
	start_time = models.TimeField()
	end_time = models.TimeField()
	active = models.BooleanField(default=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ["doctor_id", "weekday", "start_time", "id"]

	def __str__(self) -> str:
		return f"DoctorHours doctor_id={self.doctor_id} weekday={self.weekday} {self.start_time}-{self.end_time}"


class DoctorAbsence(models.Model):
	doctor = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name='doctor_absences',
	)
	start_date = models.DateField()
	end_date = models.DateField()
	reason = models.CharField(max_length=255, blank=True, null=True)
	active = models.BooleanField(default=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ["doctor_id", "start_date", "end_date", "id"]

	def __str__(self) -> str:
		return f"DoctorAbsence doctor_id={self.doctor_id} {self.start_date}-{self.end_date}"


class DoctorBreak(models.Model):
	# doctor=NULL => praxisweite Pause
	doctor = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		null=True,
		blank=True,
		on_delete=models.CASCADE,
		related_name='doctor_breaks',
	)
	date = models.DateField()
	start_time = models.TimeField()
	end_time = models.TimeField()
	reason = models.CharField(max_length=255, blank=True, null=True)
	active = models.BooleanField(default=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ["date", "start_time", "doctor_id", "id"]

	def __str__(self) -> str:
		return f"DoctorBreak date={self.date} {self.start_time}-{self.end_time} doctor_id={self.doctor_id}"


class Appointment(models.Model):
	STATUS_SCHEDULED = 'scheduled'
	STATUS_CONFIRMED = 'confirmed'
	STATUS_CANCELLED = 'cancelled'
	STATUS_COMPLETED = 'completed'

	STATUS_CHOICES = (
		(STATUS_SCHEDULED, STATUS_SCHEDULED),
		(STATUS_CONFIRMED, STATUS_CONFIRMED),
		(STATUS_CANCELLED, STATUS_CANCELLED),
		(STATUS_COMPLETED, STATUS_COMPLETED),
	)

	id = models.AutoField(primary_key=True)
	patient_id = models.IntegerField()
	type = models.ForeignKey(
		AppointmentType,
		null=True,
		blank=True,
		on_delete=models.SET_NULL,
	)
	resources = models.ManyToManyField(
		"Resource",
		through="AppointmentResource",
		related_name="appointments",
		blank=True,
	)
	doctor = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.PROTECT,
		related_name='appointments',
	)
	start_time = models.DateTimeField()
	end_time = models.DateTimeField()
	status = models.CharField(
		max_length=20,
		choices=STATUS_CHOICES,
		default=STATUS_SCHEDULED,
	)
	notes = models.TextField(blank=True, null=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ['-start_time', '-id']

	def __str__(self) -> str:
		return f"Appointment #{self.id} (patient_id={self.patient_id})"


class Resource(models.Model):
	TYPE_ROOM = "room"
	TYPE_DEVICE = "device"

	TYPE_CHOICES = (
		(TYPE_ROOM, TYPE_ROOM),
		(TYPE_DEVICE, TYPE_DEVICE),
	)

	name = models.CharField(max_length=255)
	type = models.CharField(max_length=20, choices=TYPE_CHOICES)
	color = models.CharField(max_length=7, default="#6A5ACD")
	active = models.BooleanField(default=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ["type", "name", "id"]

	def __str__(self) -> str:
		return f"{self.type}:{self.name}"


class AppointmentResource(models.Model):
	appointment = models.ForeignKey(
		Appointment,
		on_delete=models.CASCADE,
		related_name="appointment_resources",
	)
	resource = models.ForeignKey(
		Resource,
		on_delete=models.CASCADE,
		related_name="appointment_resources",
	)

	class Meta:
		unique_together = ("appointment", "resource")
		ordering = ["appointment_id", "resource_id", "id"]


class OperationType(models.Model):
	name = models.CharField(max_length=255)
	prep_duration = models.IntegerField(default=0)
	op_duration = models.IntegerField(default=0)
	post_duration = models.IntegerField(default=0)
	color = models.CharField(max_length=7, default="#8A2BE2")
	active = models.BooleanField(default=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ["name", "id"]

	def __str__(self) -> str:
		return self.name


class Operation(models.Model):
	STATUS_PLANNED = "planned"
	STATUS_CONFIRMED = "confirmed"
	STATUS_RUNNING = "running"
	STATUS_DONE = "done"
	STATUS_CANCELLED = "cancelled"

	STATUS_CHOICES = (
		(STATUS_PLANNED, STATUS_PLANNED),
		(STATUS_CONFIRMED, STATUS_CONFIRMED),
		(STATUS_RUNNING, STATUS_RUNNING),
		(STATUS_DONE, STATUS_DONE),
		(STATUS_CANCELLED, STATUS_CANCELLED),
	)

	# NOTE: Patient lives in the read-only medical DB, so we store patient_id.
	patient_id = models.IntegerField()

	primary_surgeon = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		related_name="op_primary",
		on_delete=models.CASCADE,
	)
	assistant = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		related_name="op_assistant",
		null=True,
		blank=True,
		on_delete=models.SET_NULL,
	)
	anesthesist = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		related_name="op_anesthesist",
		null=True,
		blank=True,
		on_delete=models.SET_NULL,
	)

	op_room = models.ForeignKey(
		Resource,
		on_delete=models.CASCADE,
		related_name="operations_as_room",
	)
	op_devices = models.ManyToManyField(
		Resource,
		through="OperationDevice",
		related_name="operations_as_device",
		blank=True,
	)
	op_type = models.ForeignKey(OperationType, on_delete=models.CASCADE)

	start_time = models.DateTimeField()
	end_time = models.DateTimeField()
	status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PLANNED)
	notes = models.TextField(blank=True, null=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ["-start_time", "-id"]

	def __str__(self) -> str:
		return f"Operation #{self.id} (patient_id={self.patient_id})"


class OperationDevice(models.Model):
	operation = models.ForeignKey(
		Operation,
		on_delete=models.CASCADE,
		related_name="operation_devices",
	)
	resource = models.ForeignKey(
		Resource,
		on_delete=models.CASCADE,
		related_name="operation_devices",
	)

	class Meta:
		unique_together = ("operation", "resource")
		ordering = ["operation_id", "resource_id", "id"]


class PatientFlow(models.Model):
	STATUS_REGISTERED = "registered"
	STATUS_WAITING = "waiting"
	STATUS_PREPARING = "preparing"
	STATUS_IN_TREATMENT = "in_treatment"
	STATUS_POST_TREATMENT = "post_treatment"
	STATUS_DONE = "done"

	STATUS_CHOICES = (
		(STATUS_REGISTERED, STATUS_REGISTERED),
		(STATUS_WAITING, STATUS_WAITING),
		(STATUS_PREPARING, STATUS_PREPARING),
		(STATUS_IN_TREATMENT, STATUS_IN_TREATMENT),
		(STATUS_POST_TREATMENT, STATUS_POST_TREATMENT),
		(STATUS_DONE, STATUS_DONE),
	)

	appointment = models.ForeignKey(
		Appointment,
		null=True,
		blank=True,
		on_delete=models.SET_NULL,
		related_name="patient_flows",
	)
	operation = models.ForeignKey(
		Operation,
		null=True,
		blank=True,
		on_delete=models.SET_NULL,
		related_name="patient_flows",
	)
	status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_REGISTERED)
	arrival_time = models.DateTimeField(null=True, blank=True)
	status_changed_at = models.DateTimeField(auto_now=True)
	notes = models.TextField(null=True, blank=True)

	class Meta:
		ordering = ["-status_changed_at", "-id"]

	def __str__(self) -> str:
		return f"PatientFlow #{self.id} ({self.status})"

# Create your models here.
