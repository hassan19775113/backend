from django.db import migrations, models


class Migration(migrations.Migration):

	dependencies = [
		("core", "0002_auditlog"),
	]

	operations = [
		migrations.AddField(
			model_name="user",
			name="calendar_color",
			field=models.CharField(blank=True, default="#1E90FF", max_length=7),
		),
	]
