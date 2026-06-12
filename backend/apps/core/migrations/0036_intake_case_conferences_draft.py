from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0035_alert_alleged_perpetrator_race"),
    ]

    operations = [
        migrations.AddField(
            model_name="intake",
            name="case_conferences_draft",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
