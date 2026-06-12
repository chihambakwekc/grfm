from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0033_alter_alert_perpetrator_has_access"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="alert",
            name="circumstances_of_offence",
        ),
        migrations.RemoveField(
            model_name="alert",
            name="immediate_action_taken",
        ),
        migrations.RemoveField(
            model_name="alert",
            name="services_contacted",
        ),
    ]
