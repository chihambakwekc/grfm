from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models
import re


district_code_validator = RegexValidator(
    regex=r"^[A-Z]{3}$",
    message="District code must be exactly 3 uppercase letters.",
)


def next_scoped_reference(model, prefix, district, exclude_pk=None):
    district_code = (district.code or "").strip().upper() if district else ""
    if not district_code:
        district_code = "UNK"
    stem = f"{prefix}-{district_code}-"
    qs = model.objects.filter(reference__startswith=stem)
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    highest = 0
    for reference in qs.values_list("reference", flat=True):
        match = re.match(rf"^{re.escape(stem)}(\d+)$", reference or "")
        if match:
            highest = max(highest, int(match.group(1)))
    return f"{stem}{highest + 1:03d}"


def public_alert_reference_prefix(alert):
    if alert.intake_source == "PUBLIC_ABUSE_REPORT" or alert.emergency:
        return "ABU"
    return "CMP"


class Province(models.Model):
    name = models.CharField(max_length=120, unique=True)
    code = models.CharField(max_length=12, blank=True)
    status = models.CharField(max_length=20, default="Active", choices=[("Active", "Active"), ("Inactive", "Inactive")])
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="created_provinces")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="updated_provinces")
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class District(models.Model):
    province = models.ForeignKey(Province, on_delete=models.PROTECT, related_name="districts")
    name = models.CharField(max_length=120)
    code = models.CharField(max_length=3, unique=True, validators=[district_code_validator])
    status = models.CharField(max_length=20, default="Active", choices=[("Active", "Active"), ("Inactive", "Inactive")])
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="created_districts")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="updated_districts")
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("province", "name")

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.code = (self.code or "").strip().upper()
        return super().save(*args, **kwargs)


class CaseNumberSequence(models.Model):
    district = models.ForeignKey(District, on_delete=models.PROTECT, related_name="case_number_sequences")
    year = models.PositiveIntegerField()
    next_number = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = ("district", "year")
        ordering = ("district__code", "year")

    def __str__(self):
        return f"{self.district.code}/{self.year} next {self.next_number}"


class Ward(models.Model):
    province = models.ForeignKey(Province, on_delete=models.PROTECT, related_name="wards", null=True, blank=True)
    district = models.ForeignKey(District, on_delete=models.PROTECT, related_name="wards")
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, default="Active", choices=[("Active", "Active"), ("Inactive", "Inactive")])
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="created_wards")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="updated_wards")
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("district", "name")

    def __str__(self):
        return f"{self.name}, {self.district.name}"

    def save(self, *args, **kwargs):
        if self.district_id and not self.province_id:
            self.province_id = self.district.province_id
        return super().save(*args, **kwargs)


class CommunityChildcareWorker(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="ccw_record", null=True, blank=True)
    province = models.ForeignKey(Province, on_delete=models.PROTECT, related_name="ccws", null=True, blank=True)
    district = models.ForeignKey(District, on_delete=models.PROTECT, related_name="ccws")
    ward = models.ForeignKey(Ward, on_delete=models.PROTECT, related_name="ccws", null=True, blank=True)
    full_name = models.CharField(max_length=180)
    national_id = models.CharField(max_length=80, blank=True)
    gender = models.CharField(max_length=30, blank=True)
    phone = models.CharField(max_length=60)
    email = models.EmailField(blank=True)
    physical_address = models.CharField(max_length=240, blank=True)
    status = models.CharField(max_length=20, default="Active", choices=[("Active", "Active"), ("Inactive", "Inactive")])
    date_registered = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="created_ccws")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="updated_ccws")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("full_name",)

    def __str__(self):
        return self.full_name

    def save(self, *args, **kwargs):
        if self.district_id:
            self.province_id = self.district.province_id
        return super().save(*args, **kwargs)


class PartnersInDistrict(models.Model):
    class PartnerType(models.TextChoices):
        NGO = "NGO", "NGO"
        GOVERNMENT = "Government Department", "Government Department"
        HEALTH = "Hospital/Clinic", "Hospital/Clinic"
        POLICE = "Police/VFU", "Police/VFU"
        SCHOOL = "School", "School"
        FAITH = "Faith Based Organisation", "Faith Based Organisation"
        COMMUNITY = "Community Based Organisation", "Community Based Organisation"
        SAFETY = "Place of Safety", "Place of Safety"
        LEGAL = "Legal Aid", "Legal Aid"
        OTHER = "Other", "Other"

    province = models.ForeignKey(Province, on_delete=models.PROTECT, related_name="district_partners", null=True, blank=True)
    district = models.ForeignKey(District, on_delete=models.PROTECT, related_name="district_partners")
    ward = models.ForeignKey(Ward, on_delete=models.PROTECT, related_name="district_partners", null=True, blank=True)
    partner_name = models.CharField(max_length=180)
    partner_type = models.CharField(max_length=80, choices=PartnerType.choices)
    partner_type_other = models.CharField(max_length=120, blank=True)
    services_offered = models.JSONField(default=list, blank=True)
    services_offered_other = models.CharField(max_length=180, blank=True)
    contact_person = models.CharField(max_length=160, blank=True)
    phone = models.CharField(max_length=60, blank=True)
    email = models.EmailField(blank=True)
    address = models.CharField(max_length=240, blank=True)
    operating_area = models.CharField(max_length=180, blank=True)
    status = models.CharField(max_length=20, default="Active", choices=[("Active", "Active"), ("Inactive", "Inactive")])
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="created_district_partners")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="updated_district_partners")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("district", "partner_name")
        ordering = ("partner_name",)

    def __str__(self):
        return self.partner_name

    def save(self, *args, **kwargs):
        if self.district_id:
            self.province_id = self.district.province_id
        return super().save(*args, **kwargs)


class Court(models.Model):
    class CourtType(models.TextChoices):
        MAGISTRATES = "Magistrates Court", "Magistrates Court"
        CHILDRENS = "Children's Court", "Children's Court"
        HIGH = "High Court", "High Court"
        COMMUNITY = "Community Court", "Community Court"
        OTHER = "Other", "Other"

    province = models.ForeignKey(Province, on_delete=models.PROTECT, related_name="courts", null=True, blank=True)
    district = models.ForeignKey(District, on_delete=models.PROTECT, related_name="courts")
    court_name = models.CharField(max_length=180)
    court_type = models.CharField(max_length=80, choices=CourtType.choices)
    court_type_other = models.CharField(max_length=120, blank=True)
    contact_person = models.CharField(max_length=160, blank=True)
    phone = models.CharField(max_length=60, blank=True)
    email = models.EmailField(blank=True)
    physical_address = models.CharField(max_length=240, blank=True)
    status = models.CharField(max_length=20, default="Active", choices=[("Active", "Active"), ("Inactive", "Inactive")])
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="created_courts")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="updated_courts")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("district", "court_name")
        ordering = ("court_name",)

    def __str__(self):
        return self.court_name

    def save(self, *args, **kwargs):
        if self.district_id:
            self.province_id = self.district.province_id
        return super().save(*args, **kwargs)


class Organization(models.Model):
    class Type(models.TextChoices):
        DSD = "DSD", "Department of Social Development"
        NGO = "NGO", "NGO"
        SCHOOL = "SCHOOL", "School"
        HEALTH = "HEALTH", "Health Facility"
        POLICE = "POLICE", "Police/VFU"
        CPC = "CPC", "Child Protection Committee"
        COMMUNITY = "COMMUNITY", "Community"

    name = models.CharField(max_length=180, unique=True)
    organization_type = models.CharField(max_length=30, choices=Type.choices)
    district = models.ForeignKey(District, on_delete=models.PROTECT, null=True, blank=True)

    def __str__(self):
        return self.name


class RelationshipType(models.Model):
    name = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, default="Active", choices=[("Active", "Active"), ("Inactive", "Inactive")])
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="created_relationship_types")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="updated_relationship_types")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name",)

    def __str__(self):
        return self.name


class UserProfile(models.Model):
    class Role(models.TextChoices):
        SYS_ADMIN = "SYS_ADMIN", "System Administrator"
        NATIONAL = "NATIONAL", "National"
        NATIONAL_PROGRAM = "NATIONAL_PROGRAM", "National Program"
        PROVINCIAL_HEAD = "PROVINCIAL_HEAD", "Province Head"
        DISTRICT_HEAD = "DISTRICT_HEAD", "District Head"
        DSDO = "DSDO", "DSDO"
        COMMUNITY_USER = "COMMUNITY_USER", "Community User"
        CCW = "CCW", "Community Case Worker"
        NGO = "NGO", "NGO"
        POLICE = "POLICE", "Police"
        TEACHER = "TEACHER", "Teacher"
        NURSE = "NURSE", "Nurse"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    role = models.CharField(max_length=40, choices=Role.choices)
    phone = models.CharField(max_length=40, blank=True)
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT, null=True, blank=True)
    province = models.ForeignKey(Province, on_delete=models.PROTECT, null=True, blank=True)
    district = models.ForeignKey(District, on_delete=models.PROTECT, null=True, blank=True)
    ward = models.ForeignKey(Ward, on_delete=models.PROTECT, null=True, blank=True)
    active = models.BooleanField(default=True)
    must_change_password = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username} - {self.get_role_display()}"

    @property
    def portal(self):
        return "external" if self.role in {"COMMUNITY_USER", "CCW", "NGO", "POLICE", "TEACHER", "NURSE"} else "internal"


class Alert(models.Model):
    class Status(models.TextChoices):
        SUBMITTED = "Submitted", "Submitted"
        RECEIVED = "Received by District Office", "Received by District Office"
        UNDER_REVIEW = "Under Review", "Under Review"
        MORE_INFO = "More Information Requested", "More Information Requested"
        CONVERTED = "Converted to Case", "Converted to Case"
        REFERRED = "Referred to Relevant Office", "Referred to Relevant Office"
        CLOSED = "Closed - No Further Action", "Closed - No Further Action"
        DUPLICATE = "Duplicate / Already Known", "Duplicate / Already Known"
        EMERGENCY = "Emergency Response Initiated", "Emergency Response Initiated"
        READY_INTAKE = "Ready for Intake", "Ready for Intake"
        INTAKE_PROGRESS = "Intake In Progress", "Intake In Progress"
        SUPERVISOR_REVIEW = "Pending Supervisor Review", "Pending Supervisor Review"
        APPROVED_ALLOCATION = "Approved for Allocation", "Approved for Allocation"
        ALLOCATED = "Allocated to Case Officer", "Allocated to Case Officer"
        REJECTED = "Rejected", "Rejected"

    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="submitted_alerts")
    reference = models.CharField(max_length=40, unique=True, blank=True)
    child_first_name = models.CharField(max_length=120, blank=True)
    child_surname = models.CharField(max_length=120, blank=True)
    child_alias = models.CharField(max_length=120, blank=True)
    sex = models.CharField(max_length=20, default="Unknown")
    estimated_age = models.CharField(max_length=40, blank=True, default="Unknown")
    date_of_birth = models.DateField(null=True, blank=True)
    birth_certificate_number = models.CharField(max_length=80, blank=True)
    birth_registered = models.CharField(max_length=20, default="Unknown")
    disability = models.CharField(max_length=20, default="Unknown")
    current_location = models.CharField(max_length=240, blank=True)
    home_address = models.CharField(max_length=240, blank=True)
    district = models.ForeignKey(District, on_delete=models.PROTECT, null=True, blank=True)
    ward = models.ForeignKey(Ward, on_delete=models.PROTECT, null=True, blank=True)
    village_suburb = models.CharField(max_length=160, blank=True)
    chief_name = models.CharField(max_length=160, blank=True)
    nearest_landmark = models.CharField(max_length=160, blank=True)
    nearest_school = models.CharField(max_length=160, blank=True)
    nearest_clinic = models.CharField(max_length=160, blank=True)
    caregiver_name = models.CharField(max_length=160, blank=True)
    caregiver_contact = models.CharField(max_length=80, blank=True)
    relationship_to_child = models.CharField(max_length=120, blank=True)
    protect_reporter_identity = models.BooleanField(default=False)
    intake_source = models.CharField(max_length=80, default="ALERT", blank=True)
    reporting_channel = models.CharField(max_length=120, blank=True)
    information_source_type = models.CharField(max_length=120, blank=True)
    information_source_other = models.CharField(max_length=160, blank=True)
    information_source_name = models.CharField(max_length=160, blank=True)
    information_source_surname = models.CharField(max_length=120, blank=True)
    information_source_first_names = models.CharField(max_length=160, blank=True)
    information_source_id_number = models.CharField(max_length=80, blank=True)
    information_source_sex = models.CharField(max_length=20, blank=True)
    information_source_contact = models.CharField(max_length=80, blank=True)
    information_source_email = models.EmailField(blank=True)
    information_source_address = models.CharField(max_length=240, blank=True)
    information_source_relationship_to_child = models.CharField(max_length=120, blank=True)
    information_source_reporter_type = models.CharField(max_length=120, blank=True)
    protect_source_identity = models.BooleanField(default=False)
    alternative_contact = models.CharField(max_length=80, blank=True)
    source_brief_description = models.TextField(blank=True)
    household_social_registry = models.CharField(max_length=20, blank=True, default="")
    programme = models.CharField(max_length=120, blank=True)
    concern_categories = models.JSONField(default=list, blank=True)
    incident_date = models.DateField(null=True, blank=True)
    date_reporter_became_aware = models.DateField(null=True, blank=True)
    incident_location = models.CharField(max_length=240, blank=True)
    description = models.TextField(blank=True)
    alleged_perpetrator_name = models.CharField(max_length=160, blank=True)
    alleged_perpetrator_relationship = models.CharField(max_length=120, blank=True)
    alleged_perpetrator_known = models.CharField(max_length=20, blank=True)
    alleged_perpetrator_sex = models.CharField(max_length=20, blank=True)
    alleged_perpetrator_race = models.CharField(max_length=20, blank=True)
    alleged_perpetrator_address = models.CharField(max_length=240, blank=True)
    perpetrator_has_access = models.CharField(max_length=20, blank=True, default="")
    referred_to_police = models.CharField(max_length=20, blank=True)
    police_reference_number = models.CharField(max_length=120, blank=True)
    police_referral_date = models.DateField(null=True, blank=True)
    court_appearance_scheduled = models.CharField(max_length=20, blank=True)
    court_appearance_date = models.DateField(null=True, blank=True)
    conviction_determined = models.CharField(max_length=20, blank=True)
    conviction_date = models.DateField(null=True, blank=True)
    attachments = models.JSONField(default=list, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    location_mismatch = models.BooleanField(default=False)
    emergency = models.BooleanField(default=False)
    priority = models.CharField(max_length=40, default="Medium")
    escalation_level = models.CharField(max_length=40, blank=True)
    escalation_notes = models.TextField(blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    closure_reason = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=80, choices=Status.choices, default=Status.SUBMITTED)
    internal_status = models.CharField(max_length=80, default="New")
    assigned_intake_officer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="assigned_intake_alerts")
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="assigned_grfm_alerts")
    assigned_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return self.reference or f"Alert {self.pk}"

    @property
    def child_display_name(self):
        name = " ".join(part for part in [self.child_first_name, self.child_surname] if part).strip()
        return name or self.child_alias or "Unknown child"

    def save(self, *args, **kwargs):
        if not self.reference and self.district_id:
            super().save(*args, **kwargs)
            self.reference = next_scoped_reference(Alert, public_alert_reference_prefix(self), self.district, exclude_pk=self.pk)
            return super().save(update_fields=["reference"])
        return super().save(*args, **kwargs)


class CaseInvestigation(models.Model):
    case = models.ForeignKey(Alert, on_delete=models.CASCADE, related_name="investigations")
    investigation_date = models.DateField()
    method = models.CharField(max_length=80)
    persons_contacted = models.CharField(max_length=240, blank=True)
    findings = models.TextField()
    internal_notes = models.TextField(blank=True)
    attachments = models.JSONField(default=list, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="case_investigations")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-investigation_date", "-created_at")


class CaseAction(models.Model):
    case = models.ForeignKey(Alert, on_delete=models.CASCADE, related_name="case_actions")
    action_date = models.DateField()
    action_type = models.CharField(max_length=120)
    description = models.TextField()
    outcome = models.CharField(max_length=80)
    responsible_person = models.CharField(max_length=160, blank=True)
    next_step = models.CharField(max_length=240, blank=True)
    next_follow_up_date = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="case_actions")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-action_date", "-created_at")


class CaseReferral(models.Model):
    case = models.ForeignKey(Alert, on_delete=models.CASCADE, related_name="case_referrals")
    destination = models.CharField(max_length=120)
    reason = models.TextField()
    expected_response_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=80, default="Pending")
    response_date = models.DateField(null=True, blank=True)
    response_summary = models.TextField(blank=True)
    outcome = models.CharField(max_length=80, default="Pending")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="case_referrals")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)


class CaseEscalation(models.Model):
    case = models.ForeignKey(Alert, on_delete=models.CASCADE, related_name="case_escalations")
    level = models.CharField(max_length=40)
    reason = models.CharField(max_length=160)
    notes = models.TextField(blank=True)
    escalated_to = models.CharField(max_length=160, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="case_escalations")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)


class CaseResolution(models.Model):
    case = models.ForeignKey(Alert, on_delete=models.CASCADE, related_name="case_resolutions")
    resolution_type = models.CharField(max_length=120)
    resolution_summary = models.TextField()
    corrective_action = models.TextField(blank=True)
    citizen_message = models.TextField()
    resolved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="case_resolutions")
    resolved_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-resolved_at", "-created_at")


class CitizenFeedback(models.Model):
    case = models.ForeignKey(Alert, on_delete=models.CASCADE, related_name="citizen_feedback")
    feedback_status = models.CharField(max_length=80)
    rating = models.PositiveSmallIntegerField(null=True, blank=True)
    comment = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-submitted_at",)


class CaseTimeline(models.Model):
    case = models.ForeignKey(Alert, on_delete=models.CASCADE, related_name="timeline_events")
    event_type = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="case_timeline_events")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)


class PublicSubmission(models.Model):
    class SubmissionType(models.TextChoices):
        COMPLAINT = "COMPLAINT", "Complaint"
        ABUSE = "ABUSE", "Abuse Report"
        FEEDBACK = "FEEDBACK", "Feedback"
        VOICE = "VOICE", "Voice Report"

    class Status(models.TextChoices):
        SUBMITTED = "Submitted", "Submitted"
        RECEIVED = "Received by District Office", "Received by District Office"
        UNDER_REVIEW = "Under Review", "Under Review"
        CLASSIFIED = "Classified", "Classified"
        CONVERTED = "Converted to Case", "Converted to Case"
        CLOSED = "Closed", "Closed"

    reference = models.CharField(max_length=40, unique=True, blank=True)
    submission_type = models.CharField(max_length=20, choices=SubmissionType.choices)
    programme = models.CharField(max_length=120, blank=True)
    district = models.ForeignKey(District, on_delete=models.PROTECT, related_name="public_submissions")
    ward = models.ForeignKey(Ward, on_delete=models.PROTECT, related_name="public_submissions", null=True, blank=True)
    alert = models.ForeignKey(Alert, on_delete=models.SET_NULL, related_name="public_submissions", null=True, blank=True)
    reporter_name = models.CharField(max_length=160, blank=True)
    reporter_contact = models.CharField(max_length=80, blank=True)
    reporter_email = models.EmailField(blank=True)
    anonymous = models.BooleanField(default=False)
    category = models.CharField(max_length=160, blank=True)
    priority = models.CharField(max_length=40, default="Medium")
    status = models.CharField(max_length=80, choices=Status.choices, default=Status.SUBMITTED)
    title = models.CharField(max_length=220, blank=True)
    description = models.TextField(blank=True)
    transcript = models.TextField(blank=True)
    audio_data_url = models.TextField(blank=True)
    audio_mime_type = models.CharField(max_length=120, blank=True)
    audio_duration_seconds = models.PositiveIntegerField(null=True, blank=True)
    ratings = models.JSONField(default=dict, blank=True)
    satisfaction_score = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    expected_service = models.CharField(max_length=80, blank=True)
    payment_requested = models.CharField(max_length=80, blank=True)
    payment_amount = models.CharField(max_length=80, blank=True)
    payment_requested_by = models.CharField(max_length=160, blank=True)
    household_social_registry = models.CharField(max_length=20, blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    location_mismatch = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return self.reference or f"{self.submission_type} submission"

    def save(self, *args, **kwargs):
        if self.district_id and self.ward_id and not self.ward.district_id == self.district_id:
            self.ward = None
        if not self.reference and self.district_id:
            prefix = {
                self.SubmissionType.COMPLAINT: "CMP",
                self.SubmissionType.ABUSE: "ABU",
                self.SubmissionType.FEEDBACK: "GFB",
                self.SubmissionType.VOICE: "VOR",
            }.get(self.submission_type, "PUB")
            super().save(*args, **kwargs)
            self.reference = next_scoped_reference(PublicSubmission, prefix, self.district, exclude_pk=self.pk)
            return super().save(update_fields=["reference"])
        return super().save(*args, **kwargs)


class Intake(models.Model):
    class Status(models.TextChoices):
        DRAFT = "Intake In Progress", "Intake In Progress"
        SUBMITTED = "Intake Submitted", "Intake Submitted"
        SCREENED = "Screening Completed", "Screening Completed"
        CATEGORIZED = "Categorized", "Categorized"
        SUPERVISOR_REVIEW = "Pending Supervisor Review", "Pending Supervisor Review"
        APPROVED = "Approved for Allocation", "Approved for Allocation"
        RETURNED = "Returned for Correction", "Returned for Correction"
        ALLOCATED = "Allocated to Case Officer", "Allocated to Case Officer"

    HOME_LANGUAGE_CHOICES = ("English", "Shona", "Ndebele")
    RELIGION_CHOICES = ("Christian", "Jewish", "Muslim", "Other")
    FAMILY_PERSON_CATEGORIES = ("Parent / Guardian", "Sibling", "Significant Other")
    FAMILY_INVOLVEMENT_STATUSES = ("Alive and involved", "Alive but absent", "Deceased", "Abandoned child", "Unknown whereabouts", "Separated", "Not involved")
    PREVIOUS_INVOLVEMENT_CATEGORIES = ("DCWPS", "Law Enforcement", "Court", "Agency", "Health Facility", "Other")
    PREVIOUS_INVOLVEMENT_OUTCOMES = ("Resolved", "Ongoing", "Closed", "Referred", "Unknown")
    JUVENILE_OFFENCE_TYPES = ("Assault", "Sexual Offence", "Malicious Damage to Property", "Theft", "Shoplifting", "Smoking / Sniffing", "Drug Trafficking", "Forgery", "Fraud", "Theft by Conversion", "Offence Against State and Public Order", "Wildlife Act", "Other")

    alert = models.OneToOneField(Alert, on_delete=models.PROTECT, related_name="intake", null=True, blank=True)
    temporary_case_reference = models.CharField(max_length=50, unique=True)
    intake_source = models.CharField(max_length=80, default="ALERT", blank=True)
    original_alert_snapshot = models.JSONField(default=dict, blank=True)
    opening_summary = models.JSONField(default=dict, blank=True)
    child_profile_draft = models.JSONField(default=dict, blank=True)
    household_profile_draft = models.JSONField(default=dict, blank=True)
    background_information = models.JSONField(default=dict, blank=True)
    prior_assistance = models.JSONField(default=list, blank=True)
    duplicate_result = models.CharField(max_length=240, blank=True)
    initial_screening_notes = models.TextField(blank=True)
    screening_completed_at = models.DateTimeField(null=True, blank=True)
    case_category = models.CharField(max_length=160, blank=True)
    risk_level = models.CharField(max_length=40, default="Pending")
    immediate_action_required = models.BooleanField(default=False)
    immediate_action_plan = models.TextField(blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    location_mismatch = models.BooleanField(default=False)
    supervisor_notes = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="reviewed_intakes")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    allocated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="case_allocations_made")
    allocated_at = models.DateTimeField(null=True, blank=True)
    allocated_officer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="allocated_cases")
    assessment_draft = models.JSONField(default=dict, blank=True)
    care_plan_draft = models.JSONField(default=dict, blank=True)
    care_plan_versions_draft = models.JSONField(default=list, blank=True)
    care_plan_change_logs_draft = models.JSONField(default=list, blank=True)
    case_conferences_draft = models.JSONField(default=list, blank=True)
    justice_draft = models.JSONField(default=dict, blank=True)
    referrals_draft = models.JSONField(default=list, blank=True)
    service_tracking_draft = models.JSONField(default=list, blank=True)
    case_notes_draft = models.JSONField(default=list, blank=True)
    case_documents_draft = models.JSONField(default=list, blank=True)
    monitoring_followups_draft = models.JSONField(default=list, blank=True)
    case_reviews_draft = models.JSONField(default=list, blank=True)
    assessment_completed_at = models.DateTimeField(null=True, blank=True)
    assessment_completed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="completed_assessments")
    assessment_care_plan_status = models.CharField(max_length=40, default="Draft")
    assessment_care_plan_submitted_at = models.DateTimeField(null=True, blank=True)
    assessment_care_plan_submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="submitted_assessment_care_plans")
    assessment_care_plan_reviewed_at = models.DateTimeField(null=True, blank=True)
    assessment_care_plan_reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="reviewed_assessment_care_plans")
    assessment_care_plan_review_notes = models.TextField(blank=True)
    last_case_review_at = models.DateTimeField(null=True, blank=True)
    last_case_review_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="supervisor_case_reviews")
    last_case_review_decision = models.CharField(max_length=80, blank=True)
    last_case_review_notes = models.TextField(blank=True)
    closure_status = models.CharField(max_length=40, default="Not Requested")
    closure_draft = models.JSONField(default=dict, blank=True)
    closure_history_draft = models.JSONField(default=list, blank=True)
    closure_requested_at = models.DateTimeField(null=True, blank=True)
    closure_requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="closure_requests")
    closure_reviewed_at = models.DateTimeField(null=True, blank=True)
    closure_reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="reviewed_closure_requests")
    closure_review_notes = models.TextField(blank=True)
    status = models.CharField(max_length=80, choices=Status.choices, default=Status.DRAFT)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_intakes")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.temporary_case_reference


class UpdateRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "Pending", "Pending"
        APPROVED = "Approved", "Approved"
        REJECTED = "Rejected", "Rejected"

    intake = models.ForeignKey(Intake, on_delete=models.CASCADE, related_name="update_requests")
    tab = models.CharField(max_length=80)
    requested_fields = models.JSONField(default=list, blank=True)
    reason = models.TextField()
    status = models.CharField(max_length=40, choices=Status.choices, default=Status.PENDING)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="intake_update_requests")
    requested_at = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="reviewed_update_requests")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True)

    class Meta:
        ordering = ("-requested_at",)

    def __str__(self):
        return f"{self.intake.temporary_case_reference} - {self.tab} - {self.status}"


class NotificationRule(models.Model):
    class Priority(models.TextChoices):
        INFO = "info", "Info"
        WARNING = "warning", "Warning"
        CRITICAL = "critical", "Critical"
        ESCALATED = "escalated", "Escalated"

    trigger = models.CharField(max_length=120, unique=True)
    stage = models.CharField(max_length=80, blank=True)
    title_template = models.CharField(max_length=220)
    message_template = models.TextField()
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.INFO)
    category = models.CharField(max_length=80)
    recipient_roles = models.JSONField(default=list, blank=True)
    escalation_roles = models.JSONField(default=list, blank=True)
    offset_minutes = models.IntegerField(default=0)
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("stage", "trigger")

    def __str__(self):
        return self.trigger


class Notification(models.Model):
    class Priority(models.TextChoices):
        INFO = "info", "Info"
        WARNING = "warning", "Warning"
        CRITICAL = "critical", "Critical"
        ESCALATED = "escalated", "Escalated"

    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    title = models.CharField(max_length=220)
    message = models.TextField()
    category = models.CharField(max_length=80)
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.INFO)
    target_type = models.CharField(max_length=40)
    target_id = models.CharField(max_length=80)
    action_label = models.CharField(max_length=80, default="Open")
    route = models.CharField(max_length=80)
    dedupe_key = models.CharField(max_length=180)
    read_at = models.DateTimeField(null=True, blank=True)
    due_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(fields=["recipient", "dedupe_key"], name="unique_notification_per_recipient_dedupe"),
        ]

    def __str__(self):
        return f"{self.recipient} - {self.title}"


class MoreInformationRequest(models.Model):
    alert = models.ForeignKey(Alert, on_delete=models.CASCADE, related_name="information_requests")
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="information_requests_made")
    message = models.TextField()
    response = models.TextField(blank=True)
    resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)


class AuditLog(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True)
    action = models.CharField(max_length=160)
    target_type = models.CharField(max_length=80)
    target_reference = models.CharField(max_length=80)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)


class CalendarTask(models.Model):
    title = models.CharField(max_length=160)
    detail = models.CharField(max_length=240, blank=True)
    date = models.DateField()
    urgent = models.BooleanField(default=False)
    source = models.CharField(max_length=80, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="calendar_tasks")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("date", "title")
        unique_together = ("source", "title", "date")

    def __str__(self):
        return f"{self.date} - {self.title}"
