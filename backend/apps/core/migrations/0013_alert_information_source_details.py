from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0012_alert_attachments"),
    ]

    operations = [
        migrations.AddField(
            model_name="alert",
            name="information_source_address",
            field=models.CharField(blank=True, max_length=240),
        ),
        migrations.AddField(
            model_name="alert",
            name="information_source_email",
            field=models.EmailField(blank=True, max_length=254),
        ),
        migrations.AddField(
            model_name="alert",
            name="information_source_first_names",
            field=models.CharField(blank=True, max_length=160),
        ),
        migrations.AddField(
            model_name="alert",
            name="information_source_id_number",
            field=models.CharField(blank=True, max_length=80),
        ),
        migrations.AddField(
            model_name="alert",
            name="information_source_reporter_type",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="alert",
            name="information_source_sex",
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name="alert",
            name="information_source_surname",
            field=models.CharField(blank=True, max_length=120),
        ),
    ]
