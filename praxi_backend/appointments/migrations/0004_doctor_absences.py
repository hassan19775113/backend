from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

	dependencies = [
		('appointments', '0003_hours'),
		migrations.swappable_dependency(settings.AUTH_USER_MODEL),
	]

	operations = [
		migrations.CreateModel(
			name='DoctorAbsence',
			fields=[
				('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
				('start_date', models.DateField()),
				('end_date', models.DateField()),
				('reason', models.CharField(blank=True, max_length=255, null=True)),
				('active', models.BooleanField(default=True)),
				('created_at', models.DateTimeField(auto_now_add=True)),
				('updated_at', models.DateTimeField(auto_now=True)),
				(
					'doctor',
					models.ForeignKey(
						on_delete=django.db.models.deletion.CASCADE,
						related_name='doctor_absences',
						to=settings.AUTH_USER_MODEL,
					),
				),
			],
			options={
				'ordering': ['doctor_id', 'start_date', 'end_date', 'id'],
			},
		),
	]
