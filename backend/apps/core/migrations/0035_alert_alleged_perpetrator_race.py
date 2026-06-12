from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0034_remove_alert_action_text_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="alert",
            name="alleged_perpetrator_race",
            field=models.CharField(blank=True, max_length=20),
        ),
    ]
