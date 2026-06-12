from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0002_calendar_task"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="must_change_password",
            field=models.BooleanField(default=False),
        ),
    ]
