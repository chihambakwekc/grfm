from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0036_intake_case_conferences_draft"),
    ]

    operations = [
        migrations.AddField(
            model_name="intake",
            name="justice_draft",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
