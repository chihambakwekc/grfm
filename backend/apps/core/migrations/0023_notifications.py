from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def seed_notification_rules(apps, schema_editor):
    NotificationRule = apps.get_model("core", "NotificationRule")
    defaults = [
        {
            "trigger": "alert_submitted",
            "stage": "Intake",
            "title_template": "Submitted intake needs allocation review",
            "message_template": "{reference} is waiting for district review or conversion.",
            "priority": "warning",
            "category": "Intake",
            "recipient_roles": ["DISTRICT_HEAD"],
        },
        {
            "trigger": "intake_submitted_for_review",
            "stage": "Intake",
            "title_template": "Intake submitted for review",
            "message_template": "{case_reference} is waiting for supervisor screening review.",
            "priority": "warning",
            "category": "Intake",
            "recipient_roles": ["DISTRICT_HEAD"],
        },
        {
            "trigger": "case_allocated",
            "stage": "Allocation",
            "title_template": "Case allocated to you",
            "message_template": "{case_reference} has been allocated to you for assessment and follow-up.",
            "priority": "info",
            "category": "Allocation",
            "recipient_roles": ["DSDO"],
        },
        {
            "trigger": "assessment_care_plan_submitted",
            "stage": "Care Plan",
            "title_template": "Assessment and care plan submitted",
            "message_template": "{case_reference} is waiting for supervisor assessment and care plan review.",
            "priority": "warning",
            "category": "Care Plan",
            "recipient_roles": ["DISTRICT_HEAD"],
        },
        {
            "trigger": "assessment_overdue",
            "stage": "Assessment",
            "title_template": "Assessment overdue",
            "message_template": "{case_reference} assessment is overdue.",
            "priority": "critical",
            "category": "Assessment",
            "recipient_roles": ["DSDO"],
            "escalation_roles": ["DISTRICT_HEAD"],
        },
    ]
    for item in defaults:
        NotificationRule.objects.update_or_create(trigger=item["trigger"], defaults=item)


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0022_court_court_type_other_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="NotificationRule",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("trigger", models.CharField(max_length=120, unique=True)),
                ("stage", models.CharField(blank=True, max_length=80)),
                ("title_template", models.CharField(max_length=220)),
                ("message_template", models.TextField()),
                ("priority", models.CharField(choices=[("info", "Info"), ("warning", "Warning"), ("critical", "Critical"), ("escalated", "Escalated")], default="info", max_length=20)),
                ("category", models.CharField(max_length=80)),
                ("recipient_roles", models.JSONField(blank=True, default=list)),
                ("escalation_roles", models.JSONField(blank=True, default=list)),
                ("offset_minutes", models.IntegerField(default=0)),
                ("enabled", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ("stage", "trigger"),
            },
        ),
        migrations.CreateModel(
            name="Notification",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=220)),
                ("message", models.TextField()),
                ("category", models.CharField(max_length=80)),
                ("priority", models.CharField(choices=[("info", "Info"), ("warning", "Warning"), ("critical", "Critical"), ("escalated", "Escalated")], default="info", max_length=20)),
                ("target_type", models.CharField(max_length=40)),
                ("target_id", models.CharField(max_length=80)),
                ("action_label", models.CharField(default="Open", max_length=80)),
                ("route", models.CharField(max_length=80)),
                ("dedupe_key", models.CharField(max_length=180)),
                ("read_at", models.DateTimeField(blank=True, null=True)),
                ("due_at", models.DateTimeField(blank=True, null=True)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("recipient", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="notifications", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ("-created_at",),
            },
        ),
        migrations.AddConstraint(
            model_name="notification",
            constraint=models.UniqueConstraint(fields=("recipient", "dedupe_key"), name="unique_notification_per_recipient_dedupe"),
        ),
        migrations.RunPython(seed_notification_rules, migrations.RunPython.noop),
    ]
