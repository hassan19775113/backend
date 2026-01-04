from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

	dependencies = [
		("appointments", "0007_resources"),
	]

	operations = [
		migrations.CreateModel(
			name="OperationType",
			fields=[
				("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
				("name", models.CharField(max_length=255)),
				("prep_duration", models.IntegerField(default=0)),
				("op_duration", models.IntegerField(default=0)),
				("post_duration", models.IntegerField(default=0)),
				("color", models.CharField(default="#8A2BE2", max_length=7)),
				("active", models.BooleanField(default=True)),
				("created_at", models.DateTimeField(auto_now_add=True)),
				("updated_at", models.DateTimeField(auto_now=True)),
			],
			options={
				"ordering": ["name", "id"],
			},
		),
		migrations.CreateModel(
			name="Operation",
			fields=[
				("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
				("patient_id", models.IntegerField()),
				("start_time", models.DateTimeField()),
				("end_time", models.DateTimeField()),
				(
					"status",
					models.CharField(
						choices=[
							("planned", "planned"),
							("confirmed", "confirmed"),
							("running", "running"),
							("done", "done"),
							("cancelled", "cancelled"),
						],
						default="planned",
						max_length=20,
					),
				),
				("notes", models.TextField(blank=True, null=True)),
				("created_at", models.DateTimeField(auto_now_add=True)),
				("updated_at", models.DateTimeField(auto_now=True)),
				(
					"anesthesist",
					models.ForeignKey(
						blank=True,
						null=True,
						on_delete=django.db.models.deletion.SET_NULL,
						related_name="op_anesthesist",
						to=settings.AUTH_USER_MODEL,
					),
				),
				(
					"assistant",
					models.ForeignKey(
						blank=True,
						null=True,
						on_delete=django.db.models.deletion.SET_NULL,
						related_name="op_assistant",
						to=settings.AUTH_USER_MODEL,
					),
				),
				(
					"op_room",
					models.ForeignKey(
						on_delete=django.db.models.deletion.CASCADE,
						related_name="operations_as_room",
						to="appointments.resource",
					),
				),
				(
					"op_type",
					models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="appointments.operationtype"),
				),
				(
					"primary_surgeon",
					models.ForeignKey(
						on_delete=django.db.models.deletion.CASCADE,
						related_name="op_primary",
						to=settings.AUTH_USER_MODEL,
					),
				),
			],
			options={
				"ordering": ["-start_time", "-id"],
			},
		),
		migrations.CreateModel(
			name="OperationDevice",
			fields=[
				("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
				(
					"operation",
					models.ForeignKey(
						on_delete=django.db.models.deletion.CASCADE,
						related_name="operation_devices",
						to="appointments.operation",
					),
				),
				(
					"resource",
					models.ForeignKey(
						on_delete=django.db.models.deletion.CASCADE,
						related_name="operation_devices",
						to="appointments.resource",
					),
				),
			],
			options={
				"ordering": ["operation_id", "resource_id", "id"],
				"unique_together": {("operation", "resource")},
			},
		),
		migrations.AddField(
			model_name="operation",
			name="op_devices",
			field=models.ManyToManyField(blank=True, related_name="operations_as_device", through="appointments.OperationDevice", to="appointments.resource"),
		),
	]
