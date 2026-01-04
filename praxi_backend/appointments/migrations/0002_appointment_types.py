from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

	dependencies = [
		("appointments", "0001_initial"),
	]

	operations = [
		migrations.CreateModel(
			name="AppointmentType",
			fields=[
				("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
				("name", models.CharField(max_length=100)),
				("color", models.CharField(blank=True, max_length=20, null=True)),
				("duration_minutes", models.IntegerField(blank=True, null=True)),
				("active", models.BooleanField(default=True)),
				("created_at", models.DateTimeField(auto_now_add=True)),
				("updated_at", models.DateTimeField(auto_now=True)),
			],
			options={
				"ordering": ["name", "id"],
			},
		),
		migrations.AddField(
			model_name="appointment",
			name="type",
			field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="appointments.appointmenttype"),
		),
	]
