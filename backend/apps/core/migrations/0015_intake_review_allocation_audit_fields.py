from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0014_intake_prior_assistance"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="intake",
            name="reviewed_by",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="reviewed_intakes", to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name="intake",
            name="reviewed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="intake",
            name="allocated_by",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="case_allocations_made", to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name="intake",
            name="allocated_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
