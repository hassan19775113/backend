from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("appointments", "0013_doctorhours_uniq_doctorhours_slot_active"),
    ]

    operations = [
        migrations.AddField(
            model_name="appointment",
            name="is_no_show",
            field=models.BooleanField(default=False, verbose_name="No-Show (bestaetigt)"),
        ),
    ]
