from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0038_case_location_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="PublicSubmission",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reference", models.CharField(blank=True, max_length=40, unique=True)),
                ("submission_type", models.CharField(choices=[("COMPLAINT", "Complaint"), ("ABUSE", "Abuse Report"), ("FEEDBACK", "Feedback"), ("VOICE", "Voice Report")], max_length=20)),
                ("programme", models.CharField(blank=True, max_length=120)),
                ("reporter_name", models.CharField(blank=True, max_length=160)),
                ("reporter_contact", models.CharField(blank=True, max_length=80)),
                ("reporter_email", models.EmailField(blank=True, max_length=254)),
                ("anonymous", models.BooleanField(default=False)),
                ("category", models.CharField(blank=True, max_length=160)),
                ("priority", models.CharField(default="Medium", max_length=40)),
                ("status", models.CharField(choices=[("Submitted", "Submitted"), ("Received by District Office", "Received by District Office"), ("Under Review", "Under Review"), ("Classified", "Classified"), ("Converted to Case", "Converted to Case"), ("Closed", "Closed")], default="Submitted", max_length=80)),
                ("title", models.CharField(blank=True, max_length=220)),
                ("description", models.TextField(blank=True)),
                ("transcript", models.TextField(blank=True)),
                ("audio_data_url", models.TextField(blank=True)),
                ("audio_mime_type", models.CharField(blank=True, max_length=120)),
                ("audio_duration_seconds", models.PositiveIntegerField(blank=True, null=True)),
                ("ratings", models.JSONField(blank=True, default=dict)),
                ("satisfaction_score", models.DecimalField(blank=True, decimal_places=2, max_digits=4, null=True)),
                ("expected_service", models.CharField(blank=True, max_length=80)),
                ("payment_requested", models.CharField(blank=True, max_length=80)),
                ("payment_amount", models.CharField(blank=True, max_length=80)),
                ("payment_requested_by", models.CharField(blank=True, max_length=160)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("latitude", models.FloatField(blank=True, null=True)),
                ("longitude", models.FloatField(blank=True, null=True)),
                ("location_mismatch", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("alert", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="public_submissions", to="core.alert")),
                ("district", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="public_submissions", to="core.district")),
                ("ward", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="public_submissions", to="core.ward")),
            ],
            options={
                "ordering": ("-created_at",),
            },
        ),
    ]
