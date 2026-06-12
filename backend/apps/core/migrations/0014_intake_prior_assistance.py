from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0013_alert_information_source_details"),
    ]

    operations = [
        migrations.AddField(
            model_name="intake",
            name="background_information",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="intake",
            name="prior_assistance",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
