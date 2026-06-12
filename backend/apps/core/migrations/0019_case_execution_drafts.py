from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0018_reduced_approval_workflow"),
    ]

    operations = [
        migrations.AddField(
            model_name="intake",
            name="referrals_draft",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="intake",
            name="service_tracking_draft",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="intake",
            name="case_notes_draft",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="intake",
            name="case_documents_draft",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
