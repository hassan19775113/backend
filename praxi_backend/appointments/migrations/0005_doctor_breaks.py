from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

	dependencies = [
		('appointments', '0004_doctor_absences'),
		migrations.swappable_dependency(settings.AUTH_USER_MODEL),
	]

	operations = [
		migrations.CreateModel(
			name='DoctorBreak',
			fields=[
				('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
				('date', models.DateField()),
				('start_time', models.TimeField()),
				('end_time', models.TimeField()),
				('reason', models.CharField(blank=True, max_length=255, null=True)),
				('active', models.BooleanField(default=True)),
				('created_at', models.DateTimeField(auto_now_add=True)),
				('updated_at', models.DateTimeField(auto_now=True)),
				(
					'doctor',
					models.ForeignKey(
						blank=True,
						null=True,
						on_delete=django.db.models.deletion.CASCADE,
						related_name='doctor_breaks',
						to=settings.AUTH_USER_MODEL,
					),
				),
			],
			options={
				'ordering': ['date', 'start_time', 'doctor_id', 'id'],
			},
		),
	]
