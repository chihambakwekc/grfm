from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0015_intake_review_allocation_audit_fields"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="UpdateRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("tab", models.CharField(max_length=80)),
                ("requested_fields", models.JSONField(blank=True, default=list)),
                ("reason", models.TextField()),
                ("status", models.CharField(choices=[("Pending", "Pending"), ("Approved", "Approved"), ("Rejected", "Rejected")], default="Pending", max_length=40)),
                ("requested_at", models.DateTimeField(auto_now_add=True)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("review_notes", models.TextField(blank=True)),
                ("intake", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="update_requests", to="core.intake")),
                ("requested_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="intake_update_requests", to=settings.AUTH_USER_MODEL)),
                ("reviewed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="reviewed_update_requests", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ("-requested_at",),
            },
        ),
    ]
