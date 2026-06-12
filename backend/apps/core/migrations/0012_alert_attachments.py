from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0011_intake_source_and_alert_snapshot"),
    ]

    operations = [
        migrations.AddField(
            model_name="alert",
            name="attachments",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
