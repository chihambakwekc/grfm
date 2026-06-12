from django.db import migrations, models
import django.db.models.deletion


ROLE_CHOICES = [
    ("SYS_ADMIN", "System Administrator"),
    ("DEPUTY_DIRECTOR", "Deputy Director"),
    ("DIRECTOR", "Director"),
    ("PROGRAMME_OFFICER", "Programme Officer"),
    ("PROVINCIAL_HEAD", "Provincial Head"),
    ("DISTRICT_HEAD", "District Head"),
    ("DSDO", "DSDO"),
    ("CCW", "Community Case Worker"),
    ("NGO", "NGO"),
    ("POLICE", "Police"),
    ("TEACHER", "Teacher"),
    ("NURSE", "Nurse"),
]


def normalize_roles_and_provinces(apps, schema_editor):
    UserProfile = apps.get_model("core", "UserProfile")
    legacy_map = {
        "PROVINCIAL_OFFICER": "PROVINCIAL_HEAD",
        "SENIOR_SOCIAL_WORKER": "DISTRICT_HEAD",
        "INTAKE_OFFICER": "DSDO",
        "CASE_OFFICER": "DSDO",
        "LCCW": "CCW",
        "PARTNER": "NGO",
    }

    for profile in UserProfile.objects.select_related("district"):
        next_role = legacy_map.get(profile.role)
        changed = False
        if next_role:
            profile.role = next_role
            changed = True
        if profile.district_id and not profile.province_id:
            profile.province_id = profile.district.province_id
            changed = True
        if changed:
            profile.save(update_fields=["role", "province"])


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0005_add_district_head_role"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="province",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to="core.province"),
        ),
        migrations.RunPython(normalize_roles_and_provinces, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="userprofile",
            name="role",
            field=models.CharField(choices=ROLE_CHOICES, max_length=40),
        ),
    ]
