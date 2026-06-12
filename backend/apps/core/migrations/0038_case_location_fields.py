from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0037_intake_justice_draft"),
    ]

    operations = [
        migrations.AddField(
            model_name="alert",
            name="latitude",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="alert",
            name="longitude",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="alert",
            name="location_mismatch",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="intake",
            name="latitude",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="intake",
            name="longitude",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="intake",
            name="location_mismatch",
            field=models.BooleanField(default=False),
        ),
    ]
