from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0004_expand_geography_reference_data"),
    ]

    operations = [
        migrations.AlterField(
            model_name="userprofile",
            name="role",
            field=models.CharField(
                choices=[
                    ("SYS_ADMIN", "System Administrator"),
                    ("DISTRICT_HEAD", "District Head"),
                    ("DSDO", "DSDO / District Supervisor"),
                    ("INTAKE_OFFICER", "Intake Officer"),
                    ("CASE_OFFICER", "Case Officer"),
                    ("SENIOR_SOCIAL_WORKER", "Senior Social Worker"),
                    ("PROVINCIAL_OFFICER", "Provincial Officer"),
                    ("CCW", "Community Case Worker"),
                    ("LCCW", "Lead Community Case Worker"),
                    ("PARTNER", "External Partner User"),
                ],
                max_length=40,
            ),
        ),
    ]
