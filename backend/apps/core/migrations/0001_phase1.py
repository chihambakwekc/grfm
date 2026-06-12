from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Province",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120, unique=True)),
            ],
        ),
        migrations.CreateModel(
            name="District",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("code", models.CharField(max_length=8)),
                ("province", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="districts", to="core.province")),
            ],
            options={"unique_together": {("province", "name")}},
        ),
        migrations.CreateModel(
            name="Ward",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("district", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="wards", to="core.district")),
            ],
            options={"unique_together": {("district", "name")}},
        ),
        migrations.CreateModel(
            name="Organization",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=180, unique=True)),
                ("organization_type", models.CharField(choices=[("DSD", "Department of Social Development"), ("NGO", "NGO"), ("SCHOOL", "School"), ("HEALTH", "Health Facility"), ("POLICE", "Police/VFU"), ("CPC", "Child Protection Committee"), ("COMMUNITY", "Community")], max_length=30)),
                ("district", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to="core.district")),
            ],
        ),
        migrations.CreateModel(
            name="UserProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("role", models.CharField(choices=[("SYS_ADMIN", "System Administrator"), ("DSDO", "DSDO / District Supervisor"), ("INTAKE_OFFICER", "Intake Officer"), ("CASE_OFFICER", "Case Officer"), ("SENIOR_SOCIAL_WORKER", "Senior Social Worker"), ("PROVINCIAL_OFFICER", "Provincial Officer"), ("CCW", "Community Case Worker"), ("LCCW", "Lead Community Case Worker"), ("PARTNER", "External Partner User")], max_length=40)),
                ("phone", models.CharField(blank=True, max_length=40)),
                ("active", models.BooleanField(default=True)),
                ("district", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to="core.district")),
                ("organization", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to="core.organization")),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="profile", to=settings.AUTH_USER_MODEL)),
                ("ward", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to="core.ward")),
            ],
        ),
        migrations.CreateModel(
            name="Alert",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reference", models.CharField(blank=True, max_length=40, unique=True)),
                ("child_first_name", models.CharField(blank=True, max_length=120)),
                ("child_surname", models.CharField(blank=True, max_length=120)),
                ("child_alias", models.CharField(blank=True, max_length=120)),
                ("sex", models.CharField(default="Unknown", max_length=20)),
                ("estimated_age", models.CharField(blank=True, default="Unknown", max_length=40)),
                ("date_of_birth", models.DateField(blank=True, null=True)),
                ("birth_certificate_number", models.CharField(blank=True, max_length=80)),
                ("birth_registered", models.CharField(default="Unknown", max_length=20)),
                ("disability", models.CharField(default="Unknown", max_length=20)),
                ("current_location", models.CharField(blank=True, max_length=240)),
                ("home_address", models.CharField(blank=True, max_length=240)),
                ("village_suburb", models.CharField(blank=True, max_length=160)),
                ("nearest_school", models.CharField(blank=True, max_length=160)),
                ("nearest_clinic", models.CharField(blank=True, max_length=160)),
                ("caregiver_name", models.CharField(blank=True, max_length=160)),
                ("caregiver_contact", models.CharField(blank=True, max_length=80)),
                ("relationship_to_child", models.CharField(blank=True, max_length=120)),
                ("protect_reporter_identity", models.BooleanField(default=False)),
                ("concern_categories", models.JSONField(blank=True, default=list)),
                ("danger_screening", models.JSONField(blank=True, default=dict)),
                ("incident_date", models.DateField(blank=True, null=True)),
                ("date_reporter_became_aware", models.DateField(blank=True, null=True)),
                ("incident_location", models.CharField(blank=True, max_length=240)),
                ("description", models.TextField(blank=True)),
                ("alleged_perpetrator_name", models.CharField(blank=True, max_length=160)),
                ("alleged_perpetrator_relationship", models.CharField(blank=True, max_length=120)),
                ("perpetrator_has_access", models.CharField(default="Unknown", max_length=20)),
                ("immediate_action_taken", models.TextField(blank=True)),
                ("services_contacted", models.TextField(blank=True)),
                ("emergency", models.BooleanField(default=False)),
                ("status", models.CharField(choices=[("Submitted", "Submitted"), ("Received by District Office", "Received by District Office"), ("Under Review", "Under Review"), ("More Information Requested", "More Information Requested"), ("Converted to Case", "Converted to Case"), ("Referred to Relevant Office", "Referred to Relevant Office"), ("Closed - No Further Action", "Closed - No Further Action"), ("Duplicate / Already Known", "Duplicate / Already Known"), ("Emergency Response Initiated", "Emergency Response Initiated"), ("Ready for Intake", "Ready for Intake"), ("Intake In Progress", "Intake In Progress"), ("Pending Supervisor Review", "Pending Supervisor Review"), ("Approved for Allocation", "Approved for Allocation"), ("Allocated to Case Officer", "Allocated to Case Officer")], default="Submitted", max_length=80)),
                ("internal_status", models.CharField(default="Alert Submitted", max_length=80)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("assigned_intake_officer", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="assigned_intake_alerts", to=settings.AUTH_USER_MODEL)),
                ("district", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to="core.district")),
                ("reporter", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="submitted_alerts", to=settings.AUTH_USER_MODEL)),
                ("ward", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to="core.ward")),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.CreateModel(
            name="Intake",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("temporary_case_reference", models.CharField(max_length=50, unique=True)),
                ("child_profile_draft", models.JSONField(blank=True, default=dict)),
                ("household_profile_draft", models.JSONField(blank=True, default=dict)),
                ("duplicate_result", models.CharField(blank=True, max_length=240)),
                ("initial_screening_notes", models.TextField(blank=True)),
                ("case_category", models.CharField(blank=True, max_length=160)),
                ("risk_level", models.CharField(default="Pending", max_length=40)),
                ("immediate_action_required", models.BooleanField(default=False)),
                ("immediate_action_plan", models.TextField(blank=True)),
                ("supervisor_notes", models.TextField(blank=True)),
                ("status", models.CharField(choices=[("Intake In Progress", "Intake In Progress"), ("Intake Submitted", "Intake Submitted"), ("Screening Completed", "Screening Completed"), ("Categorized", "Categorized"), ("Pending Supervisor Review", "Pending Supervisor Review"), ("Approved for Allocation", "Approved for Allocation"), ("Returned for Correction", "Returned for Correction"), ("Allocated to Case Officer", "Allocated to Case Officer")], default="Intake In Progress", max_length=80)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("alert", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="intake", to="core.alert")),
                ("allocated_officer", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="allocated_cases", to=settings.AUTH_USER_MODEL)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_intakes", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="MoreInformationRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("message", models.TextField()),
                ("response", models.TextField(blank=True)),
                ("resolved", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("responded_at", models.DateTimeField(blank=True, null=True)),
                ("alert", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="information_requests", to="core.alert")),
                ("requested_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="information_requests_made", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="AuditLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("action", models.CharField(max_length=160)),
                ("target_type", models.CharField(max_length=80)),
                ("target_reference", models.CharField(max_length=80)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("-created_at",)},
        ),
    ]
