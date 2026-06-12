from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0049_social_register_fields"),
    ]

    operations = [
        migrations.RenameField(
            model_name="alert",
            old_name="household_social_register",
            new_name="household_social_registry",
        ),
        migrations.RenameField(
            model_name="publicsubmission",
            old_name="household_social_register",
            new_name="household_social_registry",
        ),
        migrations.AlterField(
            model_name="userprofile",
            name="role",
            field=models.CharField(
                choices=[
                    ("SYS_ADMIN", "System Administrator"),
                    ("NATIONAL", "National"),
                    ("NATIONAL_PROGRAM", "National Program"),
                    ("PROVINCIAL_HEAD", "Province Head"),
                    ("DISTRICT_HEAD", "District Head"),
                    ("DSDO", "DSDO"),
                    ("COMMUNITY_USER", "Community User"),
                    ("CCW", "Community Case Worker"),
                    ("NGO", "NGO"),
                    ("POLICE", "Police"),
                    ("TEACHER", "Teacher"),
                    ("NURSE", "Nurse"),
                ],
                max_length=40,
            ),
        ),
    ]
