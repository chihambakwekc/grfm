from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0032_remove_alert_danger_screening"),
    ]

    operations = [
        migrations.AlterField(
            model_name="alert",
            name="perpetrator_has_access",
            field=models.CharField(blank=True, default="", max_length=20),
        ),
    ]
