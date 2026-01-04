from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

	dependencies = [
		("appointments", "0008_operations"),
	]

	operations = [
		migrations.CreateModel(
			name="PatientFlow",
			fields=[
				("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
				(
					"status",
					models.CharField(
						choices=[
							("registered", "registered"),
							("waiting", "waiting"),
							("preparing", "preparing"),
							("in_treatment", "in_treatment"),
							("post_treatment", "post_treatment"),
							("done", "done"),
						],
						default="registered",
						max_length=32,
					),
				),
				("arrival_time", models.DateTimeField(blank=True, null=True)),
				("status_changed_at", models.DateTimeField(auto_now=True)),
				("notes", models.TextField(blank=True, null=True)),
				(
					"appointment",
					models.ForeignKey(
						blank=True,
						null=True,
						on_delete=django.db.models.deletion.SET_NULL,
						related_name="patient_flows",
						to="appointments.appointment",
					),
				),
				(
					"operation",
					models.ForeignKey(
						blank=True,
						null=True,
						on_delete=django.db.models.deletion.SET_NULL,
						related_name="patient_flows",
						to="appointments.operation",
					),
				),
			],
			options={
				"ordering": ["-status_changed_at", "-id"],
			},
		),
	]
