from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

	dependencies = [
		("appointments", "0002_appointment_types"),
		migrations.swappable_dependency(settings.AUTH_USER_MODEL),
	]

	operations = [
		migrations.CreateModel(
			name="PracticeHours",
			fields=[
				("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
				("weekday", models.IntegerField()),
				("start_time", models.TimeField()),
				("end_time", models.TimeField()),
				("active", models.BooleanField(default=True)),
				("created_at", models.DateTimeField(auto_now_add=True)),
				("updated_at", models.DateTimeField(auto_now=True)),
			],
			options={
				"ordering": ["weekday", "start_time", "id"],
			},
		),
		migrations.CreateModel(
			name="DoctorHours",
			fields=[
				("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
				("weekday", models.IntegerField()),
				("start_time", models.TimeField()),
				("end_time", models.TimeField()),
				("active", models.BooleanField(default=True)),
				("created_at", models.DateTimeField(auto_now_add=True)),
				("updated_at", models.DateTimeField(auto_now=True)),
				(
					"doctor",
					models.ForeignKey(
						on_delete=django.db.models.deletion.CASCADE,
						related_name="doctor_hours",
						to=settings.AUTH_USER_MODEL,
					),
				),
			],
			options={
				"ordering": ["doctor_id", "weekday", "start_time", "id"],
			},
		),
	]
