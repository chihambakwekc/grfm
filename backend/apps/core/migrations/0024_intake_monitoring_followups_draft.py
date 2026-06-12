from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0023_notifications"),
    ]

    operations = [
        migrations.AddField(
            model_name="intake",
            name="monitoring_followups_draft",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
