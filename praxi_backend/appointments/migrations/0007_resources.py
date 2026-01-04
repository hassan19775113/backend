from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

	dependencies = [
		("appointments", "0006_alter_appointmenttype_color"),
	]

	operations = [
		migrations.CreateModel(
			name="Resource",
			fields=[
				("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
				("name", models.CharField(max_length=255)),
				(
					"type",
					models.CharField(choices=[("room", "room"), ("device", "device")], max_length=20),
				),
				("color", models.CharField(default="#6A5ACD", max_length=7)),
				("active", models.BooleanField(default=True)),
				("created_at", models.DateTimeField(auto_now_add=True)),
				("updated_at", models.DateTimeField(auto_now=True)),
			],
			options={
				"ordering": ["type", "name", "id"],
			},
		),
		migrations.CreateModel(
			name="AppointmentResource",
			fields=[
				("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
				(
					"appointment",
					models.ForeignKey(
						on_delete=django.db.models.deletion.CASCADE,
						related_name="appointment_resources",
						to="appointments.appointment",
					),
				),
				(
					"resource",
					models.ForeignKey(
						on_delete=django.db.models.deletion.CASCADE,
						related_name="appointment_resources",
						to="appointments.resource",
					),
				),
			],
			options={
				"ordering": ["appointment_id", "resource_id", "id"],
				"unique_together": {("appointment", "resource")},
			},
		),
		migrations.AddField(
			model_name="appointment",
			name="resources",
			field=models.ManyToManyField(blank=True, related_name="appointments", through="appointments.AppointmentResource", to="appointments.resource"),
		),
	]
