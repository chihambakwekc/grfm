from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0007_alert_source_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="alert",
            name="information_source_other",
            field=models.CharField(blank=True, max_length=160),
        ),
        migrations.AddField(
            model_name="alert",
            name="source_brief_description",
            field=models.TextField(blank=True),
        ),
    ]
