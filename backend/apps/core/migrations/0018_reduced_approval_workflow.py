from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0017_intake_sla_timestamps"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(model_name="intake", name="assessment_draft", field=models.JSONField(blank=True, default=dict)),
        migrations.AddField(model_name="intake", name="care_plan_draft", field=models.JSONField(blank=True, default=dict)),
        migrations.AddField(model_name="intake", name="assessment_care_plan_status", field=models.CharField(default="Draft", max_length=40)),
        migrations.AddField(model_name="intake", name="assessment_care_plan_submitted_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="intake", name="assessment_care_plan_reviewed_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="intake", name="assessment_care_plan_review_notes", field=models.TextField(blank=True)),
        migrations.AddField(model_name="intake", name="last_case_review_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="intake", name="last_case_review_decision", field=models.CharField(blank=True, max_length=80)),
        migrations.AddField(model_name="intake", name="last_case_review_notes", field=models.TextField(blank=True)),
        migrations.AddField(model_name="intake", name="closure_status", field=models.CharField(default="Not Requested", max_length=40)),
        migrations.AddField(model_name="intake", name="closure_requested_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="intake", name="closure_reviewed_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="intake", name="closure_review_notes", field=models.TextField(blank=True)),
        migrations.AddField(model_name="intake", name="assessment_care_plan_submitted_by", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="submitted_assessment_care_plans", to=settings.AUTH_USER_MODEL)),
        migrations.AddField(model_name="intake", name="assessment_care_plan_reviewed_by", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="reviewed_assessment_care_plans", to=settings.AUTH_USER_MODEL)),
        migrations.AddField(model_name="intake", name="last_case_review_by", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="supervisor_case_reviews", to=settings.AUTH_USER_MODEL)),
        migrations.AddField(model_name="intake", name="closure_requested_by", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="closure_requests", to=settings.AUTH_USER_MODEL)),
        migrations.AddField(model_name="intake", name="closure_reviewed_by", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="reviewed_closure_requests", to=settings.AUTH_USER_MODEL)),
    ]
