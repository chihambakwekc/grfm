from django.db import migrations, models


NEW_ROLE_CHOICES = [
    ("SYS_ADMIN", "System Administrator"),
    ("NATIONAL", "National"),
    ("NATIONAL_PROGRAM", "National Program"),
    ("PROVINCIAL_HEAD", "Province Head"),
    ("DISTRICT_HEAD", "District Head"),
    ("DSDO", "DSDO"),
    ("CCW", "Community Case Worker"),
    ("NGO", "NGO"),
    ("POLICE", "Police"),
    ("TEACHER", "Teacher"),
    ("NURSE", "Nurse"),
]


def forwards(apps, schema_editor):
    UserProfile = apps.get_model("core", "UserProfile")
    UserProfile.objects.filter(role__in=["DEPUTY_DIRECTOR", "DIRECTOR"]).update(role="NATIONAL")
    UserProfile.objects.filter(role="PROGRAMME_OFFICER").update(role="NATIONAL_PROGRAM")


def backwards(apps, schema_editor):
    UserProfile = apps.get_model("core", "UserProfile")
    UserProfile.objects.filter(role="NATIONAL").update(role="DIRECTOR")
    UserProfile.objects.filter(role="NATIONAL_PROGRAM").update(role="PROGRAMME_OFFICER")


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0039_public_submission"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
        migrations.AlterField(
            model_name="userprofile",
            name="role",
            field=models.CharField(choices=NEW_ROLE_CHOICES, max_length=40),
        ),
    ]
