from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


DEFAULT_RELATIONSHIPS = [
    "Parent",
    "Mother",
    "Father",
    "Guardian",
    "Relative",
    "Sibling",
    "Grandparent",
    "Aunt / Uncle",
    "Teacher",
    "Health worker",
    "Police officer",
    "Neighbour",
    "Community worker",
    "Caregiver",
    "Child self-report",
    "Other",
    "Unknown",
]


def seed_relationship_types(apps, schema_editor):
    RelationshipType = apps.get_model("core", "RelationshipType")
    for name in DEFAULT_RELATIONSHIPS:
        RelationshipType.objects.get_or_create(name=name, defaults={"status": "Active"})


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("core", "0029_alert_chief_name"),
    ]

    operations = [
        migrations.CreateModel(
            name="RelationshipType",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120, unique=True)),
                ("description", models.TextField(blank=True)),
                ("status", models.CharField(choices=[("Active", "Active"), ("Inactive", "Inactive")], default="Active", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="created_relationship_types", to=settings.AUTH_USER_MODEL)),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="updated_relationship_types", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("name",)},
        ),
        migrations.RunPython(seed_relationship_types, migrations.RunPython.noop),
    ]
