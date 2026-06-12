from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0031_alert_prosecution_details"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="alert",
            name="danger_screening",
        ),
    ]
