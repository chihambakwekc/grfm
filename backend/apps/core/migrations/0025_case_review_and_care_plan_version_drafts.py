from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0024_intake_monitoring_followups_draft"),
    ]

    operations = [
        migrations.AddField(
            model_name="intake",
            name="care_plan_versions_draft",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="intake",
            name="care_plan_change_logs_draft",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="intake",
            name="case_reviews_draft",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
