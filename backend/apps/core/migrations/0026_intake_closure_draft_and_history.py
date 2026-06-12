from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0025_case_review_and_care_plan_version_drafts"),
    ]

    operations = [
        migrations.AddField(
            model_name="intake",
            name="closure_draft",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="intake",
            name="closure_history_draft",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
