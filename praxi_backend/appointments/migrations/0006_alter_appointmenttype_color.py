from django.db import migrations, models


class Migration(migrations.Migration):

	dependencies = [
		("appointments", "0005_doctor_breaks"),
	]

	operations = [
		migrations.AlterField(
			model_name="appointmenttype",
			name="color",
			field=models.CharField(blank=True, default="#2E8B57", max_length=7, null=True),
		),
	]
