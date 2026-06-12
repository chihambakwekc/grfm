import base64
import html
import json
import os
from copy import deepcopy
from datetime import timedelta
from functools import lru_cache
from pathlib import Path

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Alert, AuditLog, CalendarTask, CaseAction, CaseEscalation, CaseInvestigation, CaseNumberSequence, CaseReferral, CaseResolution, CaseTimeline, CitizenFeedback, CommunityChildcareWorker, Court, District, Intake, MoreInformationRequest, Notification, NotificationRule, Organization, PartnersInDistrict, Province, PublicSubmission, RelationshipType, UpdateRequest, UserProfile, Ward
from .reporting import build_report_payload
from .serializers import (
    AlertSerializer,
    AuditLogSerializer,
    CalendarTaskSerializer,
    ChangePasswordSerializer,
    CommunityAccountSerializer,
    CommunityChildcareWorkerSerializer,
    CourtSerializer,
    DistrictSerializer,
    DistrictWriteSerializer,
    HealthSerializer,
    IntakeSerializer,
    LoginSerializer,
    MoreInformationRequestSerializer,
    NotificationRuleSerializer,
    NotificationSerializer,
    OrganizationSerializer,
    PartnersInDistrictSerializer,
    ProvinceSerializer,
    PublicSubmissionSerializer,
    RelationshipTypeSerializer,
    UpdateRequestSerializer,
    UserSerializer,
    WardSerializer,
)

User = get_user_model()

NATIONAL_ROLES = {
    UserProfile.Role.SYS_ADMIN,
    UserProfile.Role.NATIONAL,
    UserProfile.Role.NATIONAL_PROGRAM,
}
NATIONAL_ESCALATION_ROLES = {UserProfile.Role.NATIONAL_PROGRAM}
PROVINCIAL_ROLES = {UserProfile.Role.PROVINCIAL_HEAD}
DISTRICT_CASE_ROLES = {UserProfile.Role.DISTRICT_HEAD, UserProfile.Role.DSDO}
INTERNAL_ROLES = NATIONAL_ROLES | PROVINCIAL_ROLES | DISTRICT_CASE_ROLES
EXTERNAL_ROLES = {UserProfile.Role.COMMUNITY_USER, UserProfile.Role.CCW, UserProfile.Role.NGO, UserProfile.Role.POLICE, UserProfile.Role.TEACHER, UserProfile.Role.NURSE}

LEGACY_ASSESSMENT_SAFETY_KEYS = {
    "childSafe",
    "immediateDanger",
    "medicalEmergency",
    "ongoingAbuse",
    "perpetratorNearby",
    "policeNeeded",
    "alternativePlacement",
    "immediateActionRequired",
    "immediateActions",
    "immediateNotes",
    "responsibleOfficer",
    "actionDate",
    "outcome",
    "currentSafetyPosition",
    "furtherUrgentAction",
    "urgentFollowUpAction",
    "urgentFollowUpDueDate",
    "urgentFollowUpResponsible",
    "urgentFollowUpNotifySupervisor",
    "urgentFollowUpSupervisorNotifiedAt",
}


def clean_assessment_draft(value):
    if not isinstance(value, dict):
        return {}
    return {key: item for key, item in value.items() if key not in LEGACY_ASSESSMENT_SAFETY_KEYS}


def normalize_care_plan_item(value):
    if not isinstance(value, dict):
        return {}
    assistance_types = value.get("assistanceTypes") or value.get("assistance_types") or []
    if not isinstance(assistance_types, list):
        assistance_types = []
    assistance_type = value.get("assistanceType") or value.get("assistance_type") or (assistance_types[0] if assistance_types else "") or value.get("plannedAction") or value.get("intervention") or ""
    return {
        "problem": value.get("problem", ""),
        "problemArea": value.get("problemArea") or value.get("problem_area", ""),
        "assistanceType": assistance_type,
        "otherAssistanceDescription": value.get("otherAssistanceDescription") or value.get("other_assistance_description", ""),
        "goal": value.get("goal", ""),
        "plannedAction": value.get("plannedAction") or value.get("intervention", ""),
        "responsiblePerson": value.get("responsiblePerson") or value.get("responsible_person") or "Allocated Officer",
        "timeline": value.get("timeline") or value.get("deadline") or "30 Days",
        "dueDate": value.get("dueDate", ""),
        "status": value.get("status", "Planned"),
        "expectedOutcome": value.get("expectedOutcome", ""),
        "requiresCourtRecommendation": value.get("requiresCourtRecommendation") or value.get("requires_court_recommendation") or "No",
        "courtRecommendation": value.get("courtRecommendation") or value.get("court_recommendation", ""),
        "notes": value.get("notes", ""),
    }


def clean_care_plan_draft(value):
    if not isinstance(value, dict):
        return {"child_story": "", "items": []}
    items = []
    for item in value.get("items") or []:
        if not isinstance(item, dict):
            continue
        assistance_types = item.get("assistanceTypes") or item.get("assistance_types") or []
        if isinstance(assistance_types, list) and len(assistance_types) > 1:
            for assistance_type in assistance_types:
                items.append(normalize_care_plan_item({**item, "assistanceType": assistance_type, "assistanceTypes": [assistance_type], "plannedAction": assistance_type}))
        else:
            normalized = normalize_care_plan_item(item)
            if normalized:
                items.append(normalized)
    child_story = value.get("child_story") or value.get("childStory") or ""
    return {"child_story": child_story, "childStory": child_story, "items": items}


def plain_text(value, fallback=""):
    if value is None:
        return fallback
    if isinstance(value, (list, tuple)):
        joined = ", ".join(plain_text(item) for item in value if plain_text(item))
        return joined or fallback
    if isinstance(value, dict):
        return fallback
    text = str(value).strip()
    return text or fallback


def first_text(*values, fallback="Not provided"):
    for value in values:
        text = plain_text(value)
        if text:
            return text
    return fallback


def html_text(value, fallback="Not provided"):
    return html.escape(first_text(value, fallback=fallback))


def referral_pdf_logo_data_uri():
    logo_path = Path(__file__).resolve().parents[3] / "frontend" / "src" / "assets" / "grfm-icon.svg"
    if not logo_path.exists():
        return ""
    encoded = base64.b64encode(logo_path.read_bytes()).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


def cot_logo_data_uri():
    logo_path = Path(__file__).resolve().parents[3] / "frontend" / "src" / "assets" / "cot.svg"
    if not logo_path.exists():
        return ""
    encoded = base64.b64encode(logo_path.read_bytes()).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


def user_display_name(user):
    name = " ".join(part for part in [user.first_name, user.last_name] if part).strip()
    return name or user.get_username()


def user_designation(user):
    profile = getattr(user, "profile", None)
    if not profile:
        return "Not provided"
    return profile.get_role_display() if hasattr(profile, "get_role_display") else plain_text(getattr(profile, "role", ""))


def select_guardian(family_members, keywords):
    for member in family_members:
        if not isinstance(member, dict):
            continue
        descriptor = " ".join([
            plain_text(member.get("guardian_type")),
            plain_text(member.get("family_member_type")),
            plain_text(member.get("relationship_to_child")),
            plain_text(member.get("person_category")),
        ]).lower()
        if any(keyword in descriptor for keyword in keywords):
            return member
    return {}


def build_referral_pdf_html(intake, referral, referral_index, request_user):
    opening = intake.opening_summary or {}
    child = intake.child_profile_draft or {}
    household = intake.household_profile_draft or {}
    background = intake.background_information or {}
    assessment = intake.assessment_draft or {}
    alert = intake.alert
    family_members = household.get("family_members") if isinstance(household.get("family_members"), list) else household.get("guardians") or []
    father = select_guardian(family_members, ("father", "male", "grandfather", "uncle"))
    mother = select_guardian(family_members, ("mother", "female", "grandmother", "aunt"))
    officer = intake.allocated_officer or request_user
    officer_profile = getattr(officer, "profile", None)
    district = first_text(
        getattr(getattr(alert, "district", None), "name", ""),
        getattr(getattr(officer_profile, "district", None), "name", ""),
        opening.get("officer_district"),
        fallback="Not provided",
    )
    officer_org = first_text(getattr(getattr(officer_profile, "organization", None), "name", ""), "Department of Social Development")
    officer_contact = first_text(getattr(officer_profile, "phone", ""), officer.email, opening.get("officer_contact"))
    circumstances = first_text(
        background.get("child_story_or_reported_circumstances"),
        assessment.get("currentSituation"),
        assessment.get("currentFamilySituation"),
        assessment.get("presentingProblem"),
        intake.initial_screening_notes,
        referral.get("briefCircumstances"),
        fallback="",
    )
    child_birth_id = first_text(child.get("id_number"), child.get("birth_certificate_number"), getattr(alert, "birth_certificate_number", ""), fallback="Not provided")
    logo_uri = referral_pdf_logo_data_uri()
    logo_html = f'<img class="logo" src="{logo_uri}" alt="National Coat of Arms" />' if logo_uri else ""
    referral_date = first_text(referral.get("date"), fallback=timezone.localdate().isoformat())

    def row(label, value):
        return f"<tr><th>{html.escape(label)}</th><td>{html_text(value)}</td></tr>"

    def guardian_rows(member):
        return "".join([
            row("Surname", member.get("surname") if member else ""),
            row("First Name", member.get("first_names") if member else ""),
            row("Address", member.get("address") if member else ""),
            row("Telephone", member.get("telephone") if member else ""),
        ])

    return f"""
    <html>
      <head>
        <meta charset="utf-8" />
        <style>
          @page {{ size: A4; margin: 18mm 16mm; }}
          body {{ font-family: Arial, sans-serif; color: #1f2937; font-size: 11px; line-height: 1.35; }}
          .header {{ text-align: center; border-bottom: 2px solid #111827; padding-bottom: 10px; margin-bottom: 14px; }}
          .logo {{ width: 82px; height: 82px; object-fit: contain; margin-bottom: 6px; }}
          h1, h2, h3 {{ margin: 0; text-transform: uppercase; }}
          h1 {{ font-size: 15px; letter-spacing: .4px; }}
          h2 {{ font-size: 14px; margin-top: 8px; }}
          h3 {{ font-size: 12px; margin: 14px 0 6px; padding: 5px 7px; background: #eef2f7; border: 1px solid #cbd5e1; }}
          table {{ width: 100%; border-collapse: collapse; margin-bottom: 8px; }}
          th, td {{ border: 1px solid #cbd5e1; padding: 6px 7px; vertical-align: top; }}
          th {{ width: 34%; background: #f8fafc; text-align: left; font-weight: 700; }}
          .meta th {{ width: 18%; }}
          .two-col {{ display: table; width: 100%; table-layout: fixed; border-spacing: 0; }}
          .col {{ display: table-cell; width: 50%; vertical-align: top; }}
          .col:first-child {{ padding-right: 5px; }}
          .col:last-child {{ padding-left: 5px; }}
          .box {{ border: 1px solid #cbd5e1; min-height: 56px; padding: 8px; margin-bottom: 8px; white-space: pre-wrap; }}
          .signature-space {{ height: 34px; border-bottom: 1px solid #111827; margin-top: 14px; }}
          .blank-lines td {{ height: 38px; }}
        </style>
      </head>
      <body>
        <div class="header">
          {logo_html}
          <h1>Ministry of Public Service, Labour and Social Welfare</h1>
          <h2>GRFM Management System<br />Referral Form</h2>
        </div>
        <table class="meta">
          <tr><th>File No</th><td>{html_text(intake.temporary_case_reference)}</td><th>Referral Date</th><td>{html_text(referral_date)}</td></tr>
        </table>

        <h3>1. Child Details</h3>
        <table>
          {row("Surname", first_text(child.get("surname"), getattr(alert, "child_surname", ""), fallback="Not provided"))}
          {row("First Names", first_text(child.get("first_names"), getattr(alert, "child_first_name", ""), fallback="Not provided"))}
          {row("ID Number / Birth Certificate Number", child_birth_id)}
          {row("Sex", first_text(child.get("sex"), getattr(alert, "sex", ""), fallback="Not provided"))}
          {row("Date of Birth", first_text(child.get("date_of_birth"), getattr(alert, "date_of_birth", ""), fallback="Not provided"))}
          {row("Age", first_text(child.get("age"), getattr(alert, "age", ""), fallback="Not provided"))}
          {row("Case Number", intake.temporary_case_reference)}
        </table>

        <h3>2. Parent / Guardian Details</h3>
        <div class="two-col">
          <div class="col"><table><tr><th colspan="2">Father / Male Guardian</th></tr>{guardian_rows(father)}</table></div>
          <div class="col"><table><tr><th colspan="2">Mother / Female Guardian</th></tr>{guardian_rows(mother)}</table></div>
        </div>

        <h3>3. Brief Circumstances of Child</h3>
        <div class="box">{html_text(circumstances, fallback="")}</div>

        <h3>4. Reason for Referral</h3>
        <div class="box">{html_text(referral.get("reason"), fallback="")}</div>

        <h3>5. Referred By</h3>
        <table>
          {row("Referred By Name", user_display_name(officer))}
          {row("Designation", user_designation(officer))}
          {row("Organization", officer_org)}
          {row("Address", district)}
          {row("Contact Details", officer_contact)}
        </table>

        <h3>6. Referral Sent To</h3>
        <table>
          {row("Organization / Service Provider Name", first_text(referral.get("referredTo"), fallback="Not provided"))}
          {row("Address", referral.get("address"))}
          {row("Contact Details", referral.get("contactDetails"))}
          {row("Referral Type", referral.get("type"))}
          {row("Priority", referral.get("priority"))}
          {row("Expected Follow-up Date", referral.get("followUpDate"))}
        </table>

        <h3>7. Responsible Referring Signature</h3>
        <p>Responsible Referring Officer Signature:</p>
        <div class="signature-space"></div>
        <table>
          {row("Name", user_display_name(officer))}
          {row("Designation", user_designation(officer))}
          {row("Date", referral_date)}
        </table>

        <h3>8. Follow-up To Be Sent Back To Referring Agency</h3>
        <table class="blank-lines">
          {row("Phone or written confirmation that referral is received and accepted", "")}
          {row("Date Seen", "")}
          {row("Date Reported Back to Referring Organization", "")}
          {row("Action Taken / Services Provided", "")}
          {row("Name", "")}
          {row("Title", "")}
          {row("Signature", "")}
        </table>
        <p>Referral record: {html.escape(str(referral_index + 1))}</p>
      </body>
    </html>
    """


SUPERVISOR_ROLES = {UserProfile.Role.DISTRICT_HEAD} | NATIONAL_ROLES
FINAL_ALERT_STATUSES = {
    Alert.Status.CONVERTED,
    Alert.Status.SUPERVISOR_REVIEW,
    Alert.Status.APPROVED_ALLOCATION,
    Alert.Status.ALLOCATED,
    Alert.Status.REJECTED,
    Alert.Status.CLOSED,
    Alert.Status.DUPLICATE,
    Alert.Status.REFERRED,
}


def has_role(user, roles):
    return user.is_authenticated and hasattr(user, "profile") and user.profile.active and user.profile.role in roles


def audit(user, action, target, metadata=None):
    AuditLog.objects.create(
        actor=user if user.is_authenticated else None,
        action=action,
        target_type=target.__class__.__name__,
        target_reference=getattr(target, "reference", None) or getattr(target, "temporary_case_reference", "") or str(target.pk),
        metadata=metadata or {},
    )


def user_name(user):
    return user.get_full_name() or user.username


def geojson_dir():
    candidates = [
        os.environ.get("GEOJSON_DIR", ""),
        Path("/app/geo"),
        Path(__file__).resolve().parents[3] / "frontend" / "src" / "assets" / "geo",
        Path(__file__).resolve().parents[2] / "frontend" / "src" / "assets" / "geo",
    ]
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate)
        if (path / "provinces.geojson").exists() and (path / "districts.geojson").exists():
            return path
    return Path(candidates[0] or "/app/geo")


@lru_cache(maxsize=2)
def load_geojson(filename):
    with (geojson_dir() / filename).open(encoding="utf-8") as handle:
        return json.load(handle)


def feature_collection(features):
    return {"type": "FeatureCollection", "features": list(features)}


def normalized_geo_name(value):
    normalized = str(value or "").strip().casefold()
    for suffix in (" metropolitan province", " province", " metropolitan"):
        if normalized.endswith(suffix):
            normalized = normalized[: -len(suffix)].strip()
    return normalized


def geo_property_matches(feature, key, expected):
    return normalized_geo_name(feature.get("properties", {}).get(key)) == normalized_geo_name(expected)


def grfm_case_status(value):
    status_text = str(value or "").strip().lower()
    if status_text in {"new", "assigned", "in progress", "escalated", "closed"}:
        return str(value)
    if any(term in status_text for term in ["closed", "closure approved", "referred", "rejected", "duplicate", "resolved", "completed", "no further action"]):
        return "Closed"
    if any(term in status_text for term in ["escalated", "emergency", "immediate", "critical"]):
        return "Escalated"
    if any(term in status_text for term in ["assigned", "allocated"]):
        return "Assigned"
    if any(term in status_text for term in ["progress", "review", "ready", "more information", "closure requested", "returned", "intake"]):
        return "In Progress"
    return "New"


def map_user_scope(user):
    profile = user.profile
    province_name = profile.province.name if profile.province_id else ""
    district_name = profile.district.name if profile.district_id else ""
    inferred_district_name = ""
    if not district_name and profile.province_id:
        province_districts = list(District.objects.filter(province_id=profile.province_id).values_list("name", flat=True)[:2])
        if len(province_districts) == 1:
            inferred_district_name = province_districts[0]
    if has_role(user, NATIONAL_ROLES):
        level = "national"
    elif has_role(user, PROVINCIAL_ROLES):
        level = "province"
    elif has_role(user, DISTRICT_CASE_ROLES):
        level = "district" if district_name or inferred_district_name else "province" if province_name else "none"
    else:
        level = "none"
    return {
        "level": level,
        "role": profile.role,
        "province": province_name,
        "district": district_name or inferred_district_name,
    }


def scoped_map_alerts(user):
    qs = Alert.objects.select_related("district", "district__province", "ward", "assigned_intake_officer").filter(intake__isnull=True)
    if has_role(user, NATIONAL_ROLES):
        return qs
    if has_role(user, PROVINCIAL_ROLES):
        return qs.filter(district__province=user.profile.province) if user.profile.province_id else qs.none()
    if has_role(user, {UserProfile.Role.DISTRICT_HEAD}):
        if user.profile.district_id:
            return qs.filter(district=user.profile.district)
        return qs.filter(district__province=user.profile.province) if user.profile.province_id else qs.none()
    if has_role(user, {UserProfile.Role.DSDO}):
        if not user.profile.district_id:
            return qs.none()
        return qs.filter(district=user.profile.district, assigned_intake_officer=user)
    return qs.none()


def scoped_map_intakes(user):
    qs = Intake.objects.select_related("alert", "alert__district", "alert__district__province", "alert__ward", "allocated_officer", "created_by", "created_by__profile", "created_by__profile__district", "created_by__profile__district__province")
    if has_role(user, NATIONAL_ROLES):
        return qs
    if has_role(user, PROVINCIAL_ROLES):
        return qs.filter(Q(alert__district__province=user.profile.province) | Q(alert__isnull=True, created_by__profile__province=user.profile.province)) if user.profile.province_id else qs.none()
    if has_role(user, {UserProfile.Role.DISTRICT_HEAD}):
        if user.profile.district_id:
            return qs.filter(Q(alert__district=user.profile.district) | Q(alert__isnull=True, created_by__profile__district=user.profile.district))
        return qs.filter(Q(alert__district__province=user.profile.province) | Q(alert__isnull=True, created_by__profile__province=user.profile.province)) if user.profile.province_id else qs.none()
    if has_role(user, {UserProfile.Role.DSDO}):
        if not user.profile.district_id:
            return qs.none()
        return qs.filter(Q(alert__district=user.profile.district) | Q(alert__isnull=True, created_by__profile__district=user.profile.district), allocated_officer=user)
    return qs.none()


def scoped_map_public_submissions(user):
    qs = PublicSubmission.objects.select_related("district", "district__province", "ward", "alert").filter(alert__isnull=True)
    if has_role(user, NATIONAL_ROLES):
        return qs
    if has_role(user, PROVINCIAL_ROLES):
        return qs.filter(district__province=user.profile.province) if user.profile.province_id else qs.none()
    if has_role(user, {UserProfile.Role.DISTRICT_HEAD}):
        if user.profile.district_id:
            return qs.filter(district=user.profile.district)
        return qs.filter(district__province=user.profile.province) if user.profile.province_id else qs.none()
    if has_role(user, {UserProfile.Role.DSDO}):
        return qs.filter(district=user.profile.district) if user.profile.district_id else qs.none()
    return qs.none()


def map_case_type(text, emergency=False, channel=""):
    combined = f"{text} {channel}".lower()
    if emergency or "abuse" in combined or "protection" in combined or "violence" in combined:
        return "Abuse / Protection Concern"
    if "voice" in combined:
        return "Voice Report"
    if "feedback" in combined or "satisfaction" in combined:
        return "Feedback"
    if "query" in combined or "information" in combined:
        return "Information Request"
    return "Complaint"


def point_in_ring(lng, lat, ring):
    inside = False
    if not ring:
        return inside
    previous_lng, previous_lat = ring[-1]
    for current_lng, current_lat in ring:
        intersects = ((current_lat > lat) != (previous_lat > lat)) and (
            lng < (previous_lng - current_lng) * (lat - current_lat) / ((previous_lat - current_lat) or 1e-12) + current_lng
        )
        if intersects:
            inside = not inside
        previous_lng, previous_lat = current_lng, current_lat
    return inside


def point_in_geometry(lat, lng, geometry):
    if lat is None or lng is None or not geometry:
        return False
    coordinates = geometry.get("coordinates") or []
    if geometry.get("type") == "Polygon":
        return any(point_in_ring(lng, lat, ring) for ring in coordinates)
    if geometry.get("type") == "MultiPolygon":
        return any(any(point_in_ring(lng, lat, ring) for ring in polygon) for polygon in coordinates)
    return False


def gps_location_mismatch(district_name, lat, lng):
    if lat is None or lng is None or not district_name:
        return False
    district_feature = next(
        (feature for feature in load_geojson("districts.geojson").get("features", []) if feature.get("properties", {}).get("adm2_name") == district_name),
        None,
    )
    if not district_feature:
        return False
    return not point_in_geometry(lat, lng, district_feature.get("geometry"))


def district_metrics_from_cases(cases):
    metrics = {}
    for item in cases:
        district = item.get("district") or "Not captured"
        row = metrics.setdefault(district, {"open_cases": 0, "critical_cases": 0, "awaiting_assignment": 0, "response_seconds": []})
        status_text = (item.get("status") or "").lower()
        priority_text = (item.get("priority") or "").lower()
        if "closed" not in status_text and "resolved" not in status_text:
            row["open_cases"] += 1
        if priority_text in {"critical", "emergency"} or item.get("emergency"):
            row["critical_cases"] += 1
        if "assignment" in status_text or "submitted" in status_text or "review" in status_text:
            row["awaiting_assignment"] += 1
        submitted = item.get("submitted_at")
        if submitted:
            try:
                row["response_seconds"].append(max(0, (timezone.now() - submitted).total_seconds()))
            except TypeError:
                pass
    return metrics


def formatted_response_days(seconds):
    if not seconds:
        return "0.0 days"
    return f"{(sum(seconds) / len(seconds)) / 86400:.1f} days"


def map_case_from_alert(alert):
    categories = alert.concern_categories or []
    concern = ", ".join(categories) or alert.case_category if hasattr(alert, "case_category") else ""
    concern = concern or alert.description[:80] or "Complaint"
    assigned = alert.assigned_intake_officer
    district_name = alert.district.name if alert.district_id else ""
    lat = alert.latitude
    lng = alert.longitude
    return {
        "id": f"alert:{alert.reference}",
        "source_type": "alert",
        "source_id": alert.reference,
        "case_reference": alert.reference,
        "case_type": map_case_type(concern, alert.emergency, alert.reporting_channel),
        "programme": alert.programme or concern,
        "province": alert.district.province.name if alert.district_id and alert.district.province_id else "",
        "district": district_name,
        "ward": alert.ward.name if alert.ward_id else "",
        "village": alert.village_suburb,
        "latitude": lat,
        "longitude": lng,
        "priority": alert.priority or ("Critical" if alert.emergency else "High" if "abuse" in concern.lower() else "Medium"),
        "status": grfm_case_status(alert.internal_status or alert.status),
        "assigned_to": user_name(assigned) if assigned else "Unassigned",
        "submitted_at": alert.created_at,
        "submitted_at_display": timezone.localtime(alert.created_at).strftime("%d %b %Y %H:%M") if alert.created_at else "",
        "emergency": alert.emergency,
        "location_mismatch": bool(alert.location_mismatch or gps_location_mismatch(district_name, lat, lng)),
    }


def intake_district(intake):
    if intake.alert and intake.alert.district_id:
        return intake.alert.district
    return intake.created_by.profile.district if hasattr(intake.created_by, "profile") else None


def map_case_from_intake(intake):
    district = intake_district(intake)
    category = intake.case_category or (intake.opening_summary or {}).get("concern_summary") or "GRFM"
    assigned = intake.allocated_officer
    emergency = bool(intake.immediate_action_required or (intake.alert and intake.alert.emergency))
    district_name = district.name if district else ""
    lat = intake.latitude if intake.latitude is not None else (intake.alert.latitude if intake.alert else None)
    lng = intake.longitude if intake.longitude is not None else (intake.alert.longitude if intake.alert else None)
    return {
        "id": f"intake:{intake.id}",
        "source_type": "intake",
        "source_id": intake.id,
        "case_reference": intake.temporary_case_reference,
        "case_type": map_case_type(category, emergency, intake.intake_source),
        "programme": category,
        "province": district.province.name if district and district.province_id else "",
        "district": district_name,
        "ward": intake.alert.ward.name if intake.alert and intake.alert.ward_id else (intake.child_profile_draft or {}).get("ward", ""),
        "village": (intake.child_profile_draft or {}).get("village", ""),
        "latitude": lat,
        "longitude": lng,
        "priority": "Critical" if emergency else (intake.alert.priority if intake.alert and intake.alert.priority else intake.risk_level or "Medium"),
        "status": grfm_case_status(intake.status),
        "assigned_to": user_name(assigned) if assigned else "Unassigned",
        "submitted_at": intake.created_at,
        "submitted_at_display": timezone.localtime(intake.created_at).strftime("%d %b %Y %H:%M") if intake.created_at else "",
        "emergency": emergency,
        "location_mismatch": bool(intake.location_mismatch or (intake.alert and intake.alert.location_mismatch) or gps_location_mismatch(district_name, lat, lng)),
    }


def map_case_from_public_submission(submission):
    category = submission.category or submission.title or submission.get_submission_type_display()
    district_name = submission.district.name if submission.district_id else ""
    lat = submission.latitude
    lng = submission.longitude
    emergency = submission.submission_type == PublicSubmission.SubmissionType.ABUSE or (submission.priority or "").lower() == "critical"
    return {
        "id": f"public:{submission.reference or submission.id}",
        "source_type": "public_submission",
        "source_id": submission.reference or submission.id,
        "case_reference": submission.reference or f"Submission {submission.id}",
        "case_type": map_case_type(category, emergency, submission.submission_type),
        "programme": submission.programme or category,
        "province": submission.district.province.name if submission.district_id and submission.district.province_id else "",
        "district": district_name,
        "ward": submission.ward.name if submission.ward_id else "",
        "village": "",
        "latitude": lat,
        "longitude": lng,
        "priority": submission.priority or ("Critical" if emergency else "Medium"),
        "status": grfm_case_status(submission.status),
        "assigned_to": "Unassigned",
        "submitted_at": submission.created_at,
        "submitted_at_display": timezone.localtime(submission.created_at).strftime("%d %b %Y %H:%M") if submission.created_at else "",
        "emergency": emergency,
        "location_mismatch": bool(submission.location_mismatch or gps_location_mismatch(district_name, lat, lng)),
    }


class MapBoundariesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        scope = map_user_scope(request.user)
        province_geo = load_geojson("provinces.geojson")
        district_geo = load_geojson("districts.geojson")
        if scope["level"] == "national":
            province_features = province_geo.get("features", [])
            district_features = district_geo.get("features", [])
        elif scope["level"] == "province" and scope["province"]:
            province_features = [feature for feature in province_geo.get("features", []) if geo_property_matches(feature, "adm1_name", scope["province"])]
            district_features = [feature for feature in district_geo.get("features", []) if geo_property_matches(feature, "adm1_name", scope["province"])]
        elif scope["level"] == "district" and scope["district"]:
            district_features = [feature for feature in district_geo.get("features", []) if geo_property_matches(feature, "adm2_name", scope["district"])]
            province_name = district_features[0].get("properties", {}).get("adm1_name") if district_features else scope["province"]
            province_features = [feature for feature in province_geo.get("features", []) if geo_property_matches(feature, "adm1_name", province_name)]
            scope["province"] = province_name or scope["province"]
        else:
            province_features = []
            district_features = []

        map_cases = [map_case_from_alert(alert) for alert in scoped_map_alerts(request.user)]
        map_cases.extend(map_case_from_intake(intake) for intake in scoped_map_intakes(request.user))
        map_cases.extend(map_case_from_public_submission(submission) for submission in scoped_map_public_submissions(request.user))
        district_metrics = district_metrics_from_cases(map_cases)
        province_metrics = {}
        for district_name, row in district_metrics.items():
            district_feature = next((feature for feature in district_features if feature.get("properties", {}).get("adm2_name") == district_name), None)
            province_name = district_feature.get("properties", {}).get("adm1_name") if district_feature else ""
            if not province_name:
                continue
            province_row = province_metrics.setdefault(province_name, {"districts": 0, "open_cases": 0, "critical_cases": 0, "response_seconds": []})
            province_row["open_cases"] += row["open_cases"]
            province_row["critical_cases"] += row["critical_cases"]
            province_row["response_seconds"].extend(row["response_seconds"])
        for feature in province_features:
            province_name = feature.get("properties", {}).get("adm1_name")
            province_metrics.setdefault(province_name, {"districts": sum(1 for district in district_features if district.get("properties", {}).get("adm1_name") == province_name), "open_cases": 0, "critical_cases": 0, "response_seconds": []})
            province_metrics[province_name]["districts"] = sum(1 for district in district_features if district.get("properties", {}).get("adm1_name") == province_name)

        return Response({
            "scope": scope,
            "provinces": feature_collection(province_features),
            "districts": feature_collection(district_features),
            "summaries": {
                "districts": {
                    name: {
                        "openCases": row["open_cases"],
                        "criticalCases": row["critical_cases"],
                        "awaitingAssignment": row["awaiting_assignment"],
                        "averageResponseTime": formatted_response_days(row["response_seconds"]),
                    } for name, row in district_metrics.items()
                },
                "provinces": {
                    name: {
                        "districts": row["districts"],
                        "openCases": row["open_cases"],
                        "criticalCases": row["critical_cases"],
                        "averageResponseTime": formatted_response_days(row["response_seconds"]),
                    } for name, row in province_metrics.items()
                },
            },
        })


class MapCasesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        cases = [map_case_from_alert(alert) for alert in scoped_map_alerts(request.user)]
        cases.extend(map_case_from_intake(intake) for intake in scoped_map_intakes(request.user))
        cases.extend(map_case_from_public_submission(submission) for submission in scoped_map_public_submissions(request.user))
        serialized = []
        seen = set()
        for item in cases:
            key = item["id"]
            if key in seen:
                continue
            seen.add(key)
            payload = dict(item)
            payload["submitted_at"] = item["submitted_at"].isoformat() if item.get("submitted_at") else ""
            serialized.append(payload)
        return Response(serialized)


def intake_case_reference(intake):
    return intake.temporary_case_reference


def next_case_reference(district):
    if not district:
        raise ValueError("A district with a 3-letter code is required before a case number can be generated.")
    code = (district.code or "").strip().upper()
    if len(code) != 3 or not code.isalpha():
        raise ValueError("District code must be exactly 3 letters before a case number can be generated.")
    year = timezone.now().year
    with transaction.atomic():
        sequence, _ = CaseNumberSequence.objects.select_for_update().get_or_create(
            district=district,
            year=year,
            defaults={"next_number": 1},
        )
        number = sequence.next_number
        sequence.next_number = number + 1
        sequence.save(update_fields=["next_number"])
    return f"{code}/{year}/{number:04d}"


def notification_recipients(roles, district=None, province=None, exclude_user=None):
    qs = User.objects.select_related("profile").filter(is_active=True, profile__active=True, profile__role__in=roles)
    if district:
        qs = qs.filter(Q(profile__district=district) | Q(profile__role__in=NATIONAL_ROLES))
    elif province:
        qs = qs.filter(Q(profile__province=province) | Q(profile__role__in=NATIONAL_ROLES))
    if exclude_user:
        qs = qs.exclude(id=exclude_user.id)
    return qs


def create_notification(recipient, *, title, message, category, priority, target_type, target_id, action_label, route, dedupe_key, due_at=None):
    return Notification.objects.update_or_create(
        recipient=recipient,
        dedupe_key=dedupe_key,
        defaults={
            "title": title,
            "message": message,
            "category": category,
            "priority": priority,
            "target_type": target_type,
            "target_id": str(target_id),
            "action_label": action_label,
            "route": route,
            "due_at": due_at,
            "read_at": None,
            "resolved_at": None,
        },
    )[0]


def notify_users(recipients, **kwargs):
    for recipient in recipients:
        create_notification(recipient, **kwargs)


def resolve_notifications(target_type, target_id, dedupe_contains=None):
    qs = Notification.objects.filter(target_type=target_type, target_id=str(target_id), resolved_at__isnull=True)
    if dedupe_contains:
        qs = qs.filter(dedupe_key__icontains=dedupe_contains)
    qs.update(resolved_at=timezone.now())


def notify_intake_submitted(intake):
    district = intake.alert.district if intake.alert_id else getattr(intake.created_by.profile, "district", None)
    recipients = notification_recipients([UserProfile.Role.DISTRICT_HEAD], district=district, exclude_user=intake.created_by)
    notify_users(
        recipients,
        title="Intake submitted for review",
        message=f"{intake_case_reference(intake)} is waiting for supervisor screening review.",
        category="Intake",
        priority="warning",
        target_type="case",
        target_id=intake.id,
        action_label="Review intake",
        route="review",
        dedupe_key=f"intake:{intake.id}:submitted-review",
    )


def notify_intake_ready_for_allocation(intake):
    district = intake.alert.district if intake.alert_id else getattr(intake.created_by.profile, "district", None)
    recipients = notification_recipients([UserProfile.Role.DISTRICT_HEAD], district=district)
    notify_users(
        recipients,
        title="Case needs allocation",
        message=f"{intake_case_reference(intake)} is approved and needs assignment to a DSDO.",
        category="Allocation",
        priority="warning",
        target_type="case",
        target_id=intake.id,
        action_label="Allocate case",
        route="allocation",
        dedupe_key=f"intake:{intake.id}:ready-allocation",
    )


def notify_case_allocated(intake):
    if not intake.allocated_officer_id:
        return
    due_at = intake.allocated_at + timedelta(days=7) if intake.allocated_at else None
    create_notification(
        intake.allocated_officer,
        title="Case allocated to you",
        message=f"{intake_case_reference(intake)} has been allocated to you for assessment and follow-up.",
        category="Allocation",
        priority="critical" if str(intake.risk_level).upper() in {"HIGH", "CRITICAL"} else "info",
        target_type="case",
        target_id=intake.id,
        action_label="Open case",
        route="case-intake",
        due_at=due_at,
        dedupe_key=f"intake:{intake.id}:allocated:{intake.allocated_officer_id}",
    )


def notify_assessment_care_plan_submitted(intake):
    district = intake.alert.district if intake.alert_id else getattr(intake.created_by.profile, "district", None)
    recipients = notification_recipients([UserProfile.Role.DISTRICT_HEAD], district=district, exclude_user=intake.assessment_care_plan_submitted_by)
    notify_users(
        recipients,
        title="Assessment and care plan submitted",
        message=f"{intake_case_reference(intake)} is waiting for supervisor assessment and care plan review.",
        category="Care Plan",
        priority="warning",
        target_type="case",
        target_id=intake.id,
        action_label="Open submission",
        route="allocated-cases",
        dedupe_key=f"intake:{intake.id}:assessment-care-plan-submitted",
    )


def scoped_by_location(qs, user):
    if has_role(user, NATIONAL_ROLES):
        return qs
    if has_role(user, PROVINCIAL_ROLES):
        return qs.filter(province=user.profile.province) if user.profile.province_id else qs.none()
    if has_role(user, DISTRICT_CASE_ROLES | {UserProfile.Role.CCW}):
        return qs.filter(district=user.profile.district) if user.profile.district_id else qs.none()
    return qs.none()


def is_external_portal_user(user):
    return bool(user.is_authenticated and getattr(user.profile, "portal", "") == "external")


def apply_setup_filters(qs, request, name_fields=(), type_fields=()):
    province = request.query_params.get("province")
    district = request.query_params.get("district")
    ward = request.query_params.get("ward")
    status_value = request.query_params.get("status")
    type_value = request.query_params.get("type")
    search = request.query_params.get("search") or request.query_params.get("name")
    service = request.query_params.get("service")
    if province:
        qs = qs.filter(province_id=province)
    if district:
        qs = qs.filter(district_id=district)
    if ward and hasattr(qs.model, "ward"):
        qs = qs.filter(ward_id=ward)
    if status_value:
        qs = qs.filter(status=status_value)
    if type_value:
        type_q = Q()
        for field in type_fields:
            type_q |= Q(**{field: type_value})
        if type_q:
            qs = qs.filter(type_q)
    if service and qs.model is PartnersInDistrict:
        qs = qs.filter(services_offered__contains=[service])
    if search:
        name_q = Q()
        for field in name_fields:
            name_q |= Q(**{f"{field}__icontains": search})
        if name_q:
            qs = qs.filter(name_q)
    return qs


class LocationScopedSetupMixin:
    manage_roles = {UserProfile.Role.SYS_ADMIN, UserProfile.Role.DISTRICT_HEAD}

    def perform_create(self, serializer):
        extra = {"created_by": self.request.user, "updated_by": self.request.user}
        if has_role(self.request.user, {UserProfile.Role.DISTRICT_HEAD}):
            extra["district"] = self.request.user.profile.district
        serializer.save(**extra)

    def perform_update(self, serializer):
        extra = {"updated_by": self.request.user}
        if has_role(self.request.user, {UserProfile.Role.DISTRICT_HEAD}):
            extra["district"] = self.request.user.profile.district
        serializer.save(**extra)

    def can_manage_object(self, obj=None):
        user = self.request.user
        if has_role(user, NATIONAL_ROLES):
            return True
        if has_role(user, {UserProfile.Role.DISTRICT_HEAD}):
            district_id = getattr(obj, "district_id", None) if obj else self.request.data.get("district")
            return bool(user.profile.district_id and str(district_id or user.profile.district_id) == str(user.profile.district_id))
        return False

    def create(self, request, *args, **kwargs):
        if not self.can_manage_object():
            return Response({"detail": "You do not have permission to create this setup record."}, status=status.HTTP_403_FORBIDDEN)
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        if not self.can_manage_object(self.get_object()):
            return Response({"detail": "You do not have permission to update this setup record."}, status=status.HTTP_403_FORBIDDEN)
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        if not self.can_manage_object(self.get_object()):
            return Response({"detail": "You do not have permission to update this setup record."}, status=status.HTTP_403_FORBIDDEN)
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        if not self.can_manage_object(self.get_object()):
            return Response({"detail": "You do not have permission to delete this setup record."}, status=status.HTTP_403_FORBIDDEN)
        return super().destroy(request, *args, **kwargs)


class SystemAdminSetupMixin:
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

    def can_manage(self):
        return has_role(self.request.user, {UserProfile.Role.SYS_ADMIN})

    def create(self, request, *args, **kwargs):
        if not self.can_manage():
            return Response({"detail": "Only system administrators can create this setup record."}, status=status.HTTP_403_FORBIDDEN)
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        if not self.can_manage():
            return Response({"detail": "Only system administrators can update this setup record."}, status=status.HTTP_403_FORBIDDEN)
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        if not self.can_manage():
            return Response({"detail": "Only system administrators can update this setup record."}, status=status.HTTP_403_FORBIDDEN)
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        if not self.can_manage():
            return Response({"detail": "Only system administrators can delete this setup record."}, status=status.HTTP_403_FORBIDDEN)
        return super().destroy(request, *args, **kwargs)


class HealthView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        serializer = HealthSerializer({"status": "ok", "service": "GRFM-api"})
        return Response(serializer.data)


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if serializer.validated_data.get("password_change_required"):
            return Response(
                {
                    "passwordChangeRequired": True,
                    "user": serializer.validated_data["user"],
                }
            )
        return Response(
            {
                "access": serializer.validated_data["access"],
                "refresh": serializer.validated_data["refresh"],
                "user": serializer.validated_data["user"],
            }
        )


class ChangePasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.save())


class CommunityAccountView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = CommunityAccountSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(CommunityAccountSerializer(user).data, status=status.HTTP_201_CREATED)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)


class ReportsAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        payload = build_report_payload(
            request.user,
            start=request.query_params.get("start") or None,
            end=request.query_params.get("end") or None,
        )
        return Response(payload)


REPORT_TYPE_OPTIONS = {
    "GRFM Summary Report",
    "Programme Performance Report",
    "Abuse & Protection Report",
    "SLA & Response Time Report",
    "Officer Workload Report",
    "Geographic Hotspot Report",
}
OUTPUT_FORMAT_OPTIONS = {"PDF", "Excel", "PowerPoint"}
PROVINCIAL_REPORT_TYPES = REPORT_TYPE_OPTIONS
DISTRICT_HEAD_REPORT_TYPES = REPORT_TYPE_OPTIONS
DSDO_REPORT_TYPES = {"GRFM Summary Report"}


def allowed_report_types_for_user(user):
    profile = getattr(user, "profile", None)
    if not profile:
        return set()
    if profile.role in NATIONAL_ROLES:
        return REPORT_TYPE_OPTIONS
    if profile.role in PROVINCIAL_ROLES:
        return PROVINCIAL_REPORT_TYPES
    if profile.role == UserProfile.Role.DISTRICT_HEAD:
        return DISTRICT_HEAD_REPORT_TYPES
    if profile.role == UserProfile.Role.DSDO:
        return DSDO_REPORT_TYPES
    return {"GRFM Summary Report"}


def normalize_report_scope_name(value):
    text = str(value or "").strip().lower()
    for suffix in (" province", " district"):
        if text.endswith(suffix):
            text = text[: -len(suffix)]
    return " ".join(text.split())


def validate_report_generation_request(user, data):
    report_type = data.get("report_type") or ""
    output_format = data.get("output_format") or ""
    start_date = parse_date(data.get("start_date") or "")
    end_date = parse_date(data.get("end_date") or "")
    province = data.get("province") or "All Provinces"
    district = data.get("district") or "All Districts"

    if report_type not in REPORT_TYPE_OPTIONS:
        raise ValidationError({"report_type": "Select a valid report type."})
    if report_type not in allowed_report_types_for_user(user):
        raise ValidationError({"report_type": "You do not have permission to generate this report type."})
    if output_format not in OUTPUT_FORMAT_OPTIONS:
        raise ValidationError({"output_format": "Select a valid output format."})
    if not start_date or not end_date:
        raise ValidationError({"period": "Please select a reporting period."})
    if start_date > end_date:
        raise ValidationError({"start_date": "Start Date cannot be after End Date."})
    if end_date < start_date:
        raise ValidationError({"end_date": "End Date cannot be before Start Date."})

    profile = getattr(user, "profile", None)
    if not profile:
        raise ValidationError({"detail": "User profile is required for report scope."})

    if profile.role in PROVINCIAL_ROLES:
        allowed_province = profile.province.name if profile.province_id else ""
        if province != "All Provinces" and normalize_report_scope_name(province) != normalize_report_scope_name(allowed_province):
            raise ValidationError({"province": "You can generate reports only for your assigned province."})
    if profile.role in DISTRICT_CASE_ROLES:
        allowed_district = profile.district.name if profile.district_id else ""
        allowed_province = profile.district.province.name if profile.district_id else (profile.province.name if profile.province_id else "")
        if district != "All Districts" and normalize_report_scope_name(district) != normalize_report_scope_name(allowed_district):
            raise ValidationError({"district": "You can generate reports only for your assigned district."})
        if province != "All Provinces" and normalize_report_scope_name(province) != normalize_report_scope_name(allowed_province):
            raise ValidationError({"province": "You can generate reports only for your assigned province."})

    return {
        "report_type": report_type,
        "output_format": output_format,
        "start_date": start_date,
        "end_date": end_date,
        "province": province,
        "district": district,
    }


class ReportsGenerateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        validated = validate_report_generation_request(request.user, request.data)
        payload = build_report_payload(
            request.user,
            start=validated["start_date"],
            end=validated["end_date"],
            province=validated["province"],
            district=validated["district"],
            programme=request.data.get("programme"),
            case_type=request.data.get("case_type"),
            priority=request.data.get("priority"),
            status=request.data.get("status"),
            report_type=validated["report_type"],
        )
        records = request.data.get("matching_records")
        if records in ("", None):
            records = payload["summary"]["totalAlerts"] + payload["summary"]["totalIntakes"]
        metadata = {
            "report_type": validated["report_type"],
            "output_format": validated["output_format"],
            "province_filter": validated["province"],
            "district_filter": validated["district"],
            "programme_filter": request.data.get("programme") or "All Programmes",
            "case_type_filter": request.data.get("case_type") or "All Case Types",
            "priority_filter": request.data.get("priority") or "All Priorities",
            "status_filter": request.data.get("status") or "All Statuses",
            "start_date": validated["start_date"].isoformat(),
            "end_date": validated["end_date"].isoformat(),
            "records_included": int(records or 0),
        }
        AuditLog.objects.create(
            actor=request.user,
            action="Report generated",
            target_type="Report",
            target_reference=validated["report_type"],
            metadata=metadata,
        )
        generated_at = timezone.localtime(timezone.now()).strftime("%d %b %Y %H:%M")
        return Response({
            "history": {
                "dateGenerated": generated_at,
                "generatedBy": request.user.get_full_name() or request.user.username,
                "reportType": validated["report_type"],
                "outputFormat": validated["output_format"],
                "provinceFilter": metadata["province_filter"],
                "districtFilter": metadata["district_filter"],
                "programmeFilter": metadata["programme_filter"],
                "dateRange": f"{validated['start_date'].strftime('%d %b %Y')} - {validated['end_date'].strftime('%d %b %Y')}",
                "recordsIncluded": metadata["records_included"],
                "downloadLink": f"{validated['output_format']} generated",
            }
        })


class ReportsExcelExportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from openpyxl import Workbook
        validated = validate_report_generation_request(request.user, {
            "report_type": request.query_params.get("report_type") or "Custom Filtered Report",
            "output_format": "Excel",
            "start_date": request.query_params.get("start") or request.query_params.get("start_date") or "",
            "end_date": request.query_params.get("end") or request.query_params.get("end_date") or "",
            "province": request.query_params.get("province") or "All Provinces",
            "district": request.query_params.get("district") or "All Districts",
        })

        payload = build_report_payload(
            request.user,
            start=validated["start_date"],
            end=validated["end_date"],
            province=validated["province"],
            district=validated["district"],
            programme=request.query_params.get("programme"),
            case_type=request.query_params.get("case_type"),
            priority=request.query_params.get("priority"),
            status=request.query_params.get("status"),
            report_type=validated["report_type"],
        )
        workbook = Workbook()
        summary = workbook.active
        summary.title = "Summary"
        summary.append(["Metric", "Value"])
        for key, value in payload["summary"].items():
            summary.append([key, value])

        for sheet_name, rows in payload["tables"].items():
            sheet = workbook.create_sheet(sheet_name[:31])
            if not rows:
                sheet.append(["No data"])
                continue
            headers = list(rows[0].keys())
            sheet.append(headers)
            for row in rows:
                sheet.append([row.get(header, "") for header in headers])

        response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response["Content-Disposition"] = 'attachment; filename="GRFM-report.xlsx"'
        workbook.save(response)
        return response


class ReportsPdfExportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from weasyprint import HTML
        validated = validate_report_generation_request(request.user, {
            "report_type": request.query_params.get("report_type") or "Custom Filtered Report",
            "output_format": "PDF",
            "start_date": request.query_params.get("start") or request.query_params.get("start_date") or "",
            "end_date": request.query_params.get("end") or request.query_params.get("end_date") or "",
            "province": request.query_params.get("province") or "All Provinces",
            "district": request.query_params.get("district") or "All Districts",
        })

        payload = build_report_payload(
            request.user,
            start=validated["start_date"],
            end=validated["end_date"],
            province=validated["province"],
            district=validated["district"],
            programme=request.query_params.get("programme"),
            case_type=request.query_params.get("case_type"),
            priority=request.query_params.get("priority"),
            status=request.query_params.get("status"),
            report_type=validated["report_type"],
        )
        report_title = html.escape(validated["report_type"])
        logo_uri = cot_logo_data_uri()
        generated_by = html.escape(request.user.get_full_name() or request.user.username)
        period = f"{validated['start_date'].strftime('%d %b %Y')} - {validated['end_date'].strftime('%d %b %Y')}"
        summary_cards = "".join(
            f"""
            <div class="metric">
              <div class="metric-label">{html.escape(str(key).replace('_', ' '))}</div>
              <div class="metric-value">{html.escape(str(value))}</div>
            </div>
            """
            for key, value in payload["summary"].items()
        )

        def table_title(key):
            words = []
            current = ""
            for character in key:
                if character.isupper() and current:
                    words.append(current)
                    current = character
                else:
                    current += character
            if current:
                words.append(current)
            return " ".join(words).replace("_", " ").title()

        def render_table(key, rows):
            title = table_title(key)
            if not rows:
                return f"""
                <h2>{html.escape(title)}</h2>
                <table><tbody><tr><td>No records found for this section.</td></tr></tbody></table>
                """
            headers = list(rows[0].keys())
            header_html = "".join(f"<th>{html.escape(str(header))}</th>" for header in headers)
            rows_html = "".join(
                "<tr>" + "".join(f"<td>{html.escape(str(row.get(header, '')))}</td>" for header in headers) + "</tr>"
                for row in rows[:20]
            )
            return f"""
            <h2>{html.escape(title)}</h2>
            <table>
              <thead><tr>{header_html}</tr></thead>
              <tbody>{rows_html}</tbody>
            </table>
            """

        table_sections = "".join(render_table(key, rows) for key, rows in payload["tables"].items())
        html_doc = f"""
        <html>
          <head>
            <style>
              @page {{ size: A4; margin: 18mm 14mm; }}
              body {{ font-family: Arial, sans-serif; color: #0f172a; font-size: 11px; }}
              .cover {{ text-align: center; border-bottom: 3px solid #0e7a33; padding-bottom: 12px; margin-bottom: 12px; }}
              .cover img {{ width: 72px; height: 72px; object-fit: contain; }}
              .ministry {{ margin-top: 8px; font-size: 14px; letter-spacing: 1px; font-weight: 900; text-transform: uppercase; color: #0f172a; }}
              .system {{ margin-top: 3px; font-size: 12px; font-weight: 900; text-transform: uppercase; color: #0e7a33; }}
              .report-name {{ margin-top: 6px; font-size: 11px; font-weight: 800; color: #334155; }}
              .meta-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 6px 44px; margin: 12px 0 14px; color: #475569; }}
              .meta-line {{ display: grid; grid-template-columns: 92px 1fr; gap: 8px; }}
              .meta-label {{ color: #64748b; }}
              .meta-value {{ font-weight: 800; color: #0f172a; }}
              .metrics {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin: 14px 0 16px; }}
              .metric {{ border: 1px solid #d8dee8; background: #f8fafc; padding: 9px; border-radius: 4px; }}
              .metric-label {{ font-size: 8px; text-transform: uppercase; color: #64748b; font-weight: 900; }}
              .metric-value {{ margin-top: 4px; font-size: 15px; color: #0e7a33; font-weight: 900; }}
              h2 {{ margin: 16px 0 6px; color: #0f172a; font-size: 14px; }}
              table {{ width: 100%; border-collapse: collapse; margin-top: 8px; page-break-inside: avoid; }}
              th, td {{ border: 1px solid #d8dee8; padding: 7px; text-align: left; }}
              th {{ background: #0e7a33; color: #ffffff; font-size: 8px; text-transform: uppercase; letter-spacing: .4px; }}
              tr:nth-child(even) td {{ background: #f8fafc; }}
              .footer {{ margin-top: 22px; padding-top: 10px; border-top: 1px solid #d8dee8; color: #64748b; font-size: 10px; }}
            </style>
          </head>
          <body>
            <div class="cover">
              {f'<img src="{logo_uri}" />' if logo_uri else ''}
              <div class="ministry">Ministry of Public Service, Labour and Social Welfare</div>
              <div class="system">National Grievance Redress Mechanism</div>
              <div class="report-name">Report: {report_title}</div>
            </div>
            <div class="meta-grid">
              <div class="meta-line"><span class="meta-label">Report:</span><span class="meta-value">{report_title}</span></div>
              <div class="meta-line"><span class="meta-label">Period:</span><span class="meta-value">{period}</span></div>
              <div class="meta-line"><span class="meta-label">Scope:</span><span class="meta-value">{html.escape(str(payload["scope"]))}</span></div>
              <div class="meta-line"><span class="meta-label">Generated:</span><span class="meta-value">{timezone.localtime(timezone.now()).strftime('%Y-%m-%d %H:%M')}</span></div>
              <div class="meta-line"><span class="meta-label">Generated by:</span><span class="meta-value">{generated_by}</span></div>
              <div class="meta-line"><span class="meta-label">System:</span><span class="meta-value">National GRFM System</span></div>
            </div>
            <div class="metrics">{summary_cards}</div>
            {table_sections}
            <div class="footer">This report was generated by the National GRFM System and is subject to role-based access controls.</div>
          </body>
        </html>
        """
        pdf = HTML(string=html_doc).write_pdf()
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{validated["report_type"].replace(" ", "-")}.pdf"'
        return response


class ReportsPowerPointExportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        validated = validate_report_generation_request(request.user, {
            "report_type": request.query_params.get("report_type") or "Custom Filtered Report",
            "output_format": "PowerPoint",
            "start_date": request.query_params.get("start") or request.query_params.get("start_date") or "",
            "end_date": request.query_params.get("end") or request.query_params.get("end_date") or "",
            "province": request.query_params.get("province") or "All Provinces",
            "district": request.query_params.get("district") or "All Districts",
        })
        payload = build_report_payload(
            request.user,
            start=validated["start_date"],
            end=validated["end_date"],
            province=validated["province"],
            district=validated["district"],
            programme=request.query_params.get("programme"),
            case_type=request.query_params.get("case_type"),
            priority=request.query_params.get("priority"),
            status=request.query_params.get("status"),
            report_type=validated["report_type"],
        )
        logo_uri = cot_logo_data_uri()
        summary_items = "".join(f"<li><strong>{html.escape(str(key))}:</strong> {html.escape(str(value))}</li>" for key, value in payload["summary"].items())
        content = f"""
        <html>
          <head><meta charset="utf-8"><title>{html.escape(validated['report_type'])}</title></head>
          <body style="font-family:Arial,sans-serif;color:#0f172a">
            <section style="width:960px;height:540px;padding:42px;background:#f8fafc">
              {f'<img src="{logo_uri}" style="width:92px;height:92px;object-fit:contain" />' if logo_uri else ''}
              <h2>Ministry of Public Service, Labour and Social Welfare</h2>
              <h1 style="color:#0e7a33">{html.escape(validated['report_type'])}</h1>
              <p>National Grievance Redress Mechanism</p>
            </section>
            <section style="width:960px;height:540px;padding:42px">
              <h1>Report Summary</h1>
              <ul>{summary_items}</ul>
            </section>
          </body>
        </html>
        """
        response = HttpResponse(content, content_type="application/vnd.ms-powerpoint")
        response["Content-Disposition"] = f'attachment; filename="{validated["report_type"].replace(" ", "-")}.ppt"'
        return response


class UserViewSet(viewsets.ModelViewSet):
    serializer_class = UserSerializer
    queryset = User.objects.select_related("profile", "profile__organization", "profile__province", "profile__district", "profile__ward").all()

    def get_queryset(self):
        if has_role(self.request.user, NATIONAL_ROLES):
            return self.queryset
        if has_role(self.request.user, PROVINCIAL_ROLES):
            return self.queryset.filter(profile__province=self.request.user.profile.province) if self.request.user.profile.province_id else self.queryset.none()
        if has_role(self.request.user, DISTRICT_CASE_ROLES):
            if self.request.user.profile.district_id:
                return self.queryset.filter(profile__district=self.request.user.profile.district)
            if self.request.user.profile.province_id:
                return self.queryset.filter(profile__province=self.request.user.profile.province)
            return self.queryset.none()
        return self.queryset.filter(id=self.request.user.id)

    def create(self, request, *args, **kwargs):
        if not has_role(request.user, {UserProfile.Role.SYS_ADMIN}):
            return Response({"detail": "Only system administrators can create users."}, status=status.HTTP_403_FORBIDDEN)
        response = super().create(request, *args, **kwargs)
        audit(request.user, "User created", User.objects.get(id=response.data["id"]), {"role": response.data["profile"]["role"]})
        return response


class DistrictViewSet(viewsets.ModelViewSet):
    queryset = District.objects.select_related("province", "created_by", "updated_by").all().order_by("province__name", "name")

    def get_permissions(self):
        if self.action in {"list", "retrieve"}:
            return [AllowAny()]
        return super().get_permissions()

    def get_serializer_class(self):
        return DistrictWriteSerializer if self.action in {"create", "update", "partial_update"} else DistrictSerializer

    def get_queryset(self):
        qs = self.queryset
        user = self.request.user
        if not user.is_authenticated:
            qs = qs.filter(status="Active")
        elif is_external_portal_user(user):
            qs = qs.filter(status="Active")
        elif has_role(user, PROVINCIAL_ROLES):
            qs = qs.filter(province=user.profile.province) if user.profile.province_id else qs.none()
        elif has_role(user, DISTRICT_CASE_ROLES | {UserProfile.Role.CCW}):
            if user.profile.district_id:
                qs = qs.filter(id=user.profile.district_id)
            elif user.profile.province_id:
                qs = qs.filter(province=user.profile.province)
            else:
                qs = qs.none()
        elif not has_role(user, NATIONAL_ROLES | EXTERNAL_ROLES):
            qs = qs.none()
        province = self.request.query_params.get("province")
        status_value = self.request.query_params.get("status")
        search = self.request.query_params.get("search") or self.request.query_params.get("name")
        if province:
            qs = qs.filter(province_id=province)
        if status_value:
            qs = qs.filter(status=status_value)
        if search:
            qs = qs.filter(name__icontains=search)
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

    def create(self, request, *args, **kwargs):
        if not has_role(request.user, NATIONAL_ROLES):
            return Response({"detail": "Only National Admin can create districts."}, status=status.HTTP_403_FORBIDDEN)
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        if not has_role(request.user, NATIONAL_ROLES):
            return Response({"detail": "Only National Admin can update districts."}, status=status.HTTP_403_FORBIDDEN)
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        if not has_role(request.user, NATIONAL_ROLES):
            return Response({"detail": "Only National Admin can delete districts."}, status=status.HTTP_403_FORBIDDEN)
        return super().destroy(request, *args, **kwargs)


class ProvinceViewSet(viewsets.ModelViewSet):
    serializer_class = ProvinceSerializer
    queryset = Province.objects.select_related("created_by", "updated_by").all().order_by("name")

    def get_permissions(self):
        if self.action in {"list", "retrieve"}:
            return [AllowAny()]
        return super().get_permissions()

    def get_queryset(self):
        qs = self.queryset
        user = self.request.user
        if not user.is_authenticated:
            qs = qs.filter(status="Active")
        elif is_external_portal_user(user):
            qs = qs.filter(status="Active")
        elif has_role(user, PROVINCIAL_ROLES):
            qs = qs.filter(id=user.profile.province_id) if user.profile.province_id else qs.none()
        elif has_role(user, DISTRICT_CASE_ROLES | {UserProfile.Role.CCW}):
            if user.profile.district_id:
                qs = qs.filter(id=user.profile.district.province_id)
            elif user.profile.province_id:
                qs = qs.filter(id=user.profile.province_id)
            else:
                qs = qs.none()
        elif not has_role(user, NATIONAL_ROLES | EXTERNAL_ROLES):
            qs = qs.none()
        search = self.request.query_params.get("search") or self.request.query_params.get("name")
        status_value = self.request.query_params.get("status")
        if search:
            qs = qs.filter(name__icontains=search)
        if status_value:
            qs = qs.filter(status=status_value)
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

    def create(self, request, *args, **kwargs):
        if not has_role(request.user, NATIONAL_ROLES):
            return Response({"detail": "Only National Admin can create provinces."}, status=status.HTTP_403_FORBIDDEN)
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        if not has_role(request.user, NATIONAL_ROLES):
            return Response({"detail": "Only National Admin can update provinces."}, status=status.HTTP_403_FORBIDDEN)
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        if not has_role(request.user, NATIONAL_ROLES):
            return Response({"detail": "Only National Admin can delete provinces."}, status=status.HTTP_403_FORBIDDEN)
        return super().destroy(request, *args, **kwargs)


class WardViewSet(LocationScopedSetupMixin, viewsets.ModelViewSet):
    serializer_class = WardSerializer
    queryset = Ward.objects.select_related("province", "district", "created_by", "updated_by").all().order_by("district__name", "name")

    def get_permissions(self):
        if self.action in {"list", "retrieve"}:
            return [AllowAny()]
        return super().get_permissions()

    def get_queryset(self):
        if not self.request.user.is_authenticated or is_external_portal_user(self.request.user):
            return apply_setup_filters(self.queryset.filter(status="Active"), self.request, name_fields=("name",))
        return apply_setup_filters(scoped_by_location(self.queryset, self.request.user), self.request, name_fields=("name",))


class CommunityChildcareWorkerViewSet(LocationScopedSetupMixin, viewsets.ModelViewSet):
    serializer_class = CommunityChildcareWorkerSerializer
    queryset = CommunityChildcareWorker.objects.select_related("province", "district", "ward", "created_by", "updated_by").all()

    def get_queryset(self):
        return apply_setup_filters(scoped_by_location(self.queryset, self.request.user), self.request, name_fields=("full_name", "phone", "national_id"), type_fields=("gender",))


class PartnersInDistrictViewSet(LocationScopedSetupMixin, viewsets.ModelViewSet):
    serializer_class = PartnersInDistrictSerializer
    queryset = PartnersInDistrict.objects.select_related("province", "district", "created_by", "updated_by").all()

    def get_queryset(self):
        return apply_setup_filters(scoped_by_location(self.queryset, self.request.user), self.request, name_fields=("partner_name", "contact_person", "phone", "email"), type_fields=("partner_type",))


class CourtViewSet(LocationScopedSetupMixin, viewsets.ModelViewSet):
    serializer_class = CourtSerializer
    queryset = Court.objects.select_related("province", "district", "created_by", "updated_by").all()

    def get_queryset(self):
        return apply_setup_filters(scoped_by_location(self.queryset, self.request.user), self.request, name_fields=("court_name", "contact_person", "phone", "email"), type_fields=("court_type",))


class OrganizationViewSet(viewsets.ModelViewSet):
    serializer_class = OrganizationSerializer
    queryset = Organization.objects.all().order_by("name")

    def get_permissions(self):
        if self.action in {"list", "retrieve"}:
            return [AllowAny()]
        return super().get_permissions()

    def create(self, request, *args, **kwargs):
        if not has_role(request.user, {UserProfile.Role.SYS_ADMIN}):
            return Response({"detail": "Only system administrators can create organizations."}, status=status.HTTP_403_FORBIDDEN)
        return super().create(request, *args, **kwargs)


class RelationshipTypeViewSet(SystemAdminSetupMixin, viewsets.ModelViewSet):
    serializer_class = RelationshipTypeSerializer
    queryset = RelationshipType.objects.select_related("created_by", "updated_by").all().order_by("name")

    def get_permissions(self):
        if self.action in {"list", "retrieve"}:
            return [AllowAny()]
        return super().get_permissions()

    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return apply_setup_filters(self.queryset.filter(status="Active"), self.request, name_fields=("name",))
        return super().get_queryset()

    def get_queryset(self):
        qs = self.queryset
        status_value = self.request.query_params.get("status")
        search = self.request.query_params.get("search") or self.request.query_params.get("name")
        if status_value:
            qs = qs.filter(status=status_value)
        if search:
            qs = qs.filter(Q(name__icontains=search) | Q(description__icontains=search))
        return qs


class PublicSubmissionViewSet(viewsets.ModelViewSet):
    serializer_class = PublicSubmissionSerializer
    lookup_field = "reference"
    queryset = PublicSubmission.objects.select_related("district", "district__province", "ward", "alert").all()

    def get_permissions(self):
        if self.action == "create":
            return [AllowAny()]
        return super().get_permissions()

    def get_queryset(self):
        user = self.request.user
        qs = self.queryset
        submission_type = self.request.query_params.get("type")
        status_value = self.request.query_params.get("status")
        search = self.request.query_params.get("search")
        if has_role(user, DISTRICT_CASE_ROLES):
            if user.profile.district_id:
                qs = qs.filter(district=user.profile.district)
            elif user.profile.province_id:
                qs = qs.filter(district__province=user.profile.province)
            else:
                qs = qs.none()
        elif has_role(user, PROVINCIAL_ROLES):
            qs = qs.filter(district__province=user.profile.province) if user.profile.province_id else qs.none()
        elif not has_role(user, NATIONAL_ROLES):
            qs = qs.none()
        if submission_type:
            qs = qs.filter(submission_type=submission_type)
        if status_value:
            qs = qs.filter(status=status_value)
        if search:
            qs = qs.filter(
                Q(reference__icontains=search)
                | Q(programme__icontains=search)
                | Q(category__icontains=search)
                | Q(title__icontains=search)
                | Q(description__icontains=search)
                | Q(transcript__icontains=search)
                | Q(district__name__icontains=search)
            )
        return qs

    def perform_create(self, serializer):
        submission = serializer.save()
        submission_route = {
            PublicSubmission.SubmissionType.COMPLAINT: "complaints",
            PublicSubmission.SubmissionType.ABUSE: "abuse-reports",
            PublicSubmission.SubmissionType.VOICE: "voice-reports",
            PublicSubmission.SubmissionType.FEEDBACK: "feedback",
        }.get(submission.submission_type, "case-alerts")
        recipients = notification_recipients([UserProfile.Role.DISTRICT_HEAD], district=submission.district)
        notify_users(
            recipients,
            title=f"{submission.get_submission_type_display()} received",
            message=f"{submission.reference} was submitted to {submission.district.name}.",
            category="Alert",
            priority="critical" if submission.priority in {"Critical", "High"} else "info",
            target_type="alert",
            target_id=submission.alert.reference if submission.alert_id else submission.reference,
            action_label="Review submission",
            route=submission_route,
            dedupe_key=f"public-submission:{submission.id}:received",
        )
        if submission.priority in {"Critical", "High"}:
            notify_users(
                notification_recipients(NATIONAL_ESCALATION_ROLES),
                title=f"National escalation: {submission.get_submission_type_display()}",
                message=f"{submission.reference} was escalated from {submission.district.name}.",
                category="Escalation",
                priority="escalated",
                target_type="alert",
                target_id=submission.alert.reference if submission.alert_id else submission.reference,
                action_label="Review escalation",
                route=submission_route,
                dedupe_key=f"public-submission:{submission.id}:national-program",
            )

    @action(detail=True, methods=["post"])
    def classify(self, request, reference=None):
        submission = self.get_object()
        if not has_role(request.user, DISTRICT_CASE_ROLES | NATIONAL_ROLES | PROVINCIAL_ROLES):
            return Response({"detail": "You do not have permission to classify public submissions."}, status=status.HTTP_403_FORBIDDEN)
        allowed_fields = {"category", "priority", "status", "title", "description", "metadata"}
        updates = {key: request.data[key] for key in allowed_fields if key in request.data}
        for key, value in updates.items():
            setattr(submission, key, value)
        submission.save(update_fields=[*updates.keys(), "updated_at"] if updates else ["updated_at"])
        audit(request.user, "Public submission classified", submission)
        return Response(PublicSubmissionSerializer(submission, context={"request": request}).data)


class AlertViewSet(viewsets.ModelViewSet):
    serializer_class = AlertSerializer
    lookup_field = "reference"
    queryset = Alert.objects.select_related("reporter", "reporter__profile", "district", "ward", "assigned_intake_officer").prefetch_related(
        "information_requests",
        "investigations",
        "case_actions",
        "case_referrals",
        "case_escalations",
        "case_resolutions",
        "citizen_feedback",
        "timeline_events",
    )

    def get_permissions(self):
        if self.action == "create":
            return [AllowAny()]
        return super().get_permissions()

    def get_queryset(self):
        user = self.request.user
        qs = self.queryset
        if has_role(user, EXTERNAL_ROLES):
            return qs.filter(reporter=user)
        if has_role(user, DISTRICT_CASE_ROLES):
            if user.profile.district_id:
                return qs.filter(district=user.profile.district)
            if user.profile.province_id:
                return qs.filter(district__province=user.profile.province)
            return qs.none()
        if has_role(user, PROVINCIAL_ROLES):
            return qs.filter(district__province=user.profile.province) if user.profile.province_id else qs.none()
        if has_role(user, NATIONAL_ROLES):
            return qs
        return qs.none()

    def create(self, request, *args, **kwargs):
        if request.user.is_authenticated and not has_role(request.user, EXTERNAL_ROLES | INTERNAL_ROLES):
            return Response({"detail": "You do not have permission to submit alerts."}, status=status.HTTP_403_FORBIDDEN)
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        alert = serializer.save()
        if alert.latitude is not None and alert.longitude is not None:
            mismatch = gps_location_mismatch(alert.district.name if alert.district_id else "", alert.latitude, alert.longitude)
            if mismatch != alert.location_mismatch:
                alert.location_mismatch = mismatch
                alert.save(update_fields=["location_mismatch"])
        recipients = notification_recipients([UserProfile.Role.DISTRICT_HEAD], district=alert.district, exclude_user=alert.reporter)
        notify_users(
            recipients,
            title="Submitted intake needs allocation review",
            message=f"{alert.reference} is waiting for district review or conversion.",
            category="Intake",
            priority="critical" if alert.emergency else "warning",
            target_type="alert",
            target_id=alert.reference,
            action_label="Open alert",
            route="triage",
            dedupe_key=f"alert:{alert.id}:submitted",
        )
        if alert.emergency:
            notify_users(
                notification_recipients(NATIONAL_ESCALATION_ROLES),
                title="National escalation: emergency alert",
                message=f"{alert.reference} was escalated from {alert.district.name if alert.district_id else 'an unknown district'}.",
                category="Escalation",
                priority="escalated",
                target_type="alert",
                target_id=alert.reference,
                action_label="Review escalation",
                route="triage",
                dedupe_key=f"alert:{alert.id}:national-program",
            )

    @action(detail=True, methods=["post"])
    def triage(self, request, reference=None):
        alert = self.get_object()
        action_name = request.data.get("action")
        if not has_role(request.user, DISTRICT_CASE_ROLES | {UserProfile.Role.SYS_ADMIN}):
            return Response({"detail": "You do not have permission to triage alerts."}, status=status.HTTP_403_FORBIDDEN)
        if alert.status in FINAL_ALERT_STATUSES:
            return Response({"detail": f"Alert actions are locked because this alert is already {alert.status}."}, status=status.HTTP_400_BAD_REQUEST)

        if action_name == "accept":
            alert.status = Alert.Status.READY_INTAKE
            alert.internal_status = "In Progress"
        elif action_name == "request_more_information":
            message = request.data.get("message", "Please provide more information.")
            MoreInformationRequest.objects.create(alert=alert, requested_by=request.user, message=message)
            alert.status = Alert.Status.MORE_INFO
            alert.internal_status = "In Progress"
        elif action_name == "duplicate":
            alert.status = Alert.Status.DUPLICATE
            alert.internal_status = "Closed"
        elif action_name == "refer":
            alert.status = Alert.Status.REFERRED
            alert.internal_status = "Closed"
        elif action_name == "close":
            alert.status = Alert.Status.UNDER_REVIEW
            alert.internal_status = "In Progress"
        elif action_name == "approve_closure":
            if not has_role(request.user, {UserProfile.Role.DISTRICT_HEAD, UserProfile.Role.SYS_ADMIN}):
                return Response({"detail": "Only a supervisor can approve closure requests."}, status=status.HTTP_403_FORBIDDEN)
            alert.status = Alert.Status.CLOSED
            alert.internal_status = "Closed"
        elif action_name == "reject_closure":
            if not has_role(request.user, {UserProfile.Role.DISTRICT_HEAD, UserProfile.Role.SYS_ADMIN}):
                return Response({"detail": "Only a supervisor can reject closure requests."}, status=status.HTTP_403_FORBIDDEN)
            alert.status = Alert.Status.UNDER_REVIEW
            alert.internal_status = "In Progress"
        elif action_name == "reject":
            alert.status = Alert.Status.REJECTED
            alert.internal_status = "Closed"
            alert.emergency = False
        elif action_name == "emergency":
            alert.status = Alert.Status.EMERGENCY
            alert.internal_status = "Escalated"
            alert.emergency = True
            alert.priority = request.data.get("priority") or alert.priority
            alert.escalation_level = request.data.get("escalation_level") or alert.escalation_level
            alert.escalation_notes = request.data.get("escalation_notes") or alert.escalation_notes
        elif action_name == "assign_intake":
            officer_id = request.data.get("officer_id")
            officer = User.objects.filter(id=officer_id, profile__role=UserProfile.Role.DSDO).first()
            if not officer:
                return Response({"detail": "Select a valid intake officer."}, status=status.HTTP_400_BAD_REQUEST)
            alert.status = Alert.Status.ALLOCATED
            alert.assigned_intake_officer = officer
            alert.internal_status = "Assigned"
            alert.assigned_by = request.user
            alert.assigned_at = timezone.now()
            CaseTimeline.objects.create(case=alert, event_type="Case assigned", description=f"Assigned to {officer.get_full_name() or officer.username}.", user=request.user)
            resolve_notifications("alert", alert.reference, "submitted")
            resolve_notifications("alert", alert.reference, "public-submission")
            notify_users(
                [officer],
                title="Case assigned to you",
                message=f"{alert.reference} has been assigned to you for investigation and response.",
                category="Assignment",
                priority="warning",
                target_type="alert",
                target_id=alert.reference,
                action_label="Open case",
                route="triage",
                dedupe_key=f"alert:{alert.id}:assigned:{officer.id}",
            )
        else:
            return Response({"detail": "Unknown triage action."}, status=status.HTTP_400_BAD_REQUEST)

        alert.save()
        audit(request.user, f"Triage action: {action_name}", alert)
        return Response(AlertSerializer(alert, context={"request": request}).data)

    @action(detail=True, methods=["post"], url_path="case-workflow")
    def case_workflow(self, request, reference=None):
        alert = self.get_object()
        action_type = request.data.get("action_type")
        if not has_role(request.user, DISTRICT_CASE_ROLES | {UserProfile.Role.SYS_ADMIN}):
            return Response({"detail": "You do not have permission to update case work."}, status=status.HTTP_403_FORBIDDEN)
        if has_role(request.user, {UserProfile.Role.DSDO}) and alert.assigned_intake_officer_id != request.user.id:
            return Response({"detail": "Only the assigned officer can update this case workspace."}, status=status.HTTP_403_FORBIDDEN)

        today = timezone.localdate()

        def posted_date(name, default=None):
            raw = request.data.get(name)
            return parse_date(raw) if raw else default

        def add_timeline(event_type, description):
            CaseTimeline.objects.create(case=alert, event_type=event_type, description=description, user=request.user)

        if action_type == "start_investigation":
            alert.internal_status = "Investigation"
            add_timeline("Investigation started", "Investigation workspace opened by assigned officer.")
            if alert.assigned_intake_officer_id:
                resolve_notifications("alert", alert.reference, f"assigned:{alert.assigned_intake_officer_id}")
        elif action_type == "investigation":
            method = request.data.get("method", "")
            findings = request.data.get("findings", "")
            if not method or not findings:
                return Response({"detail": "Investigation method and findings are required."}, status=status.HTTP_400_BAD_REQUEST)
            CaseInvestigation.objects.create(
                case=alert,
                investigation_date=posted_date("investigation_date", today),
                method=method,
                persons_contacted=request.data.get("persons_contacted", ""),
                findings=findings,
                internal_notes=request.data.get("internal_notes", ""),
                attachments=request.data.get("attachments") or [],
                created_by=request.user,
            )
            alert.internal_status = "Investigation"
            add_timeline("Investigation note added", findings[:240])
            if alert.assigned_intake_officer_id:
                resolve_notifications("alert", alert.reference, f"assigned:{alert.assigned_intake_officer_id}")
        elif action_type == "case_action":
            CaseAction.objects.create(
                case=alert,
                action_date=posted_date("action_date", today),
                action_type=request.data.get("action_type_value", "Other"),
                description=request.data.get("description", ""),
                outcome=request.data.get("outcome", "In Progress"),
                responsible_person=request.data.get("responsible_person", ""),
                next_step=request.data.get("next_step", ""),
                next_follow_up_date=posted_date("next_follow_up_date"),
                created_by=request.user,
            )
            alert.internal_status = "Investigation"
            add_timeline("Action added", request.data.get("description", "Case action added.")[:240])
        elif action_type == "referral":
            referral = CaseReferral.objects.create(
                case=alert,
                destination=request.data.get("destination", "Other"),
                reason=request.data.get("reason", ""),
                expected_response_date=posted_date("expected_response_date"),
                notes=request.data.get("notes", ""),
                created_by=request.user,
            )
            alert.internal_status = "Awaiting Referral Response"
            add_timeline("Referral created", f"Referred to {referral.destination}.")
            notify_users(
                [alert.reporter],
                title="Case referred",
                message=f"{alert.reference} has been referred to {referral.destination} for response.",
                category="Referral",
                priority="info",
                target_type="alert",
                target_id=alert.reference,
                action_label="Track case",
                route="triage",
                dedupe_key=f"alert:{alert.id}:referral:{referral.id}:citizen",
            )
        elif action_type == "referral_response":
            referral = alert.case_referrals.order_by("-created_at").first()
            if not referral:
                return Response({"detail": "No referral exists for this case."}, status=status.HTTP_400_BAD_REQUEST)
            referral.response_date = posted_date("response_date", today)
            referral.response_summary = request.data.get("response_summary", "")
            referral.outcome = request.data.get("outcome", "Pending")
            referral.status = referral.outcome
            referral.save()
            add_timeline("Referral response received", referral.response_summary[:240])
        elif action_type == "escalation":
            escalation = CaseEscalation.objects.create(
                case=alert,
                level=request.data.get("level", "Provincial"),
                reason=request.data.get("reason", "Other"),
                notes=request.data.get("notes", ""),
                escalated_to=request.data.get("escalated_to", ""),
                created_by=request.user,
            )
            alert.internal_status = "Escalated"
            alert.escalation_level = escalation.level
            alert.escalation_notes = escalation.notes
            add_timeline("Case escalated", f"Escalated to {escalation.level}: {escalation.reason}.")
            roles = PROVINCIAL_ROLES if escalation.level.lower().startswith("prov") else NATIONAL_ESCALATION_ROLES
            notify_users(
                notification_recipients(roles, province=alert.district.province if alert.district_id else None),
                title="Case escalated",
                message=f"{alert.reference} has been escalated to {escalation.level}: {escalation.reason}.",
                category="Escalation",
                priority="escalated",
                target_type="alert",
                target_id=alert.reference,
                action_label="Review case",
                route="triage",
                dedupe_key=f"alert:{alert.id}:escalated:{escalation.id}",
            )
            notify_users(
                [alert.reporter],
                title="Case escalated",
                message=f"{alert.reference} has been escalated for further review.",
                category="Escalation",
                priority="info",
                target_type="alert",
                target_id=alert.reference,
                action_label="Track case",
                route="triage",
                dedupe_key=f"alert:{alert.id}:escalated:{escalation.id}:citizen",
            )
        elif action_type == "resolution":
            if not alert.investigations.exists():
                return Response({"detail": "Investigation findings are required before resolution."}, status=status.HTTP_400_BAD_REQUEST)
            summary = request.data.get("resolution_summary", "")
            corrective_action = request.data.get("corrective_action", "")
            closure_reason = request.data.get("closure_reason", "")
            feedback_status = request.data.get("feedback_status", "")
            if not summary or not corrective_action or not closure_reason or not feedback_status:
                return Response({"detail": "Citizen feedback status, resolution summary, corrective action taken and closure reason are required."}, status=status.HTTP_400_BAD_REQUEST)
            citizen_message = request.data.get("citizen_message", "") or summary
            resolved_at = timezone.now()
            CaseResolution.objects.create(
                case=alert,
                resolution_type=request.data.get("resolution_type", "Resolved"),
                resolution_summary=summary,
                corrective_action=corrective_action,
                citizen_message=citizen_message,
                resolved_by=request.user,
                resolved_at=resolved_at,
            )
            CitizenFeedback.objects.create(
                case=alert,
                feedback_status=feedback_status,
                comment=request.data.get("feedback_comment", ""),
            )
            alert.internal_status = "Closure Requested"
            alert.closure_reason = closure_reason
            alert.resolved_at = resolved_at
            add_timeline("Resolution recorded", summary[:240])
            add_timeline("Closure requested", closure_reason[:240])
            if alert.assigned_intake_officer_id:
                resolve_notifications("alert", alert.reference, f"assigned:{alert.assigned_intake_officer_id}")
            notify_users(
                notification_recipients([UserProfile.Role.DISTRICT_HEAD], district=alert.district, exclude_user=request.user),
                title="Closure request submitted",
                message=f"{alert.reference} has a closure request waiting for review.",
                category="Care Plan",
                priority="warning",
                target_type="alert",
                target_id=alert.reference,
                action_label="Review closure",
                route="triage",
                dedupe_key=f"alert:{alert.id}:closure-requested",
            )
        elif action_type == "citizen_feedback":
            CitizenFeedback.objects.create(
                case=alert,
                feedback_status=request.data.get("feedback_status", "No Response"),
                rating=request.data.get("rating") or None,
                comment=request.data.get("comment", ""),
            )
            add_timeline("Citizen feedback received", request.data.get("feedback_status", "No Response"))
        elif action_type == "close":
            if not alert.case_resolutions.exists():
                return Response({"detail": "Resolution summary is required before closure."}, status=status.HTTP_400_BAD_REQUEST)
            closure_reason = request.data.get("closure_reason", "")
            if not closure_reason:
                return Response({"detail": "Closure reason is required."}, status=status.HTTP_400_BAD_REQUEST)
            alert.internal_status = "Closed"
            alert.status = Alert.Status.CLOSED
            alert.closure_reason = closure_reason
            alert.closed_at = timezone.now()
            add_timeline("Case closed", closure_reason)
            notify_users(
                [alert.reporter],
                title="Case closed",
                message=f"{alert.reference} has been closed. Reason: {closure_reason}.",
                category="Closure",
                priority="info",
                target_type="alert",
                target_id=alert.reference,
                action_label="Track case",
                route="triage",
                dedupe_key=f"alert:{alert.id}:closed:{alert.closed_at.isoformat()}",
            )
        elif action_type == "review_closure":
            if not has_role(request.user, {UserProfile.Role.DISTRICT_HEAD, UserProfile.Role.SYS_ADMIN}):
                return Response({"detail": "Only a district head can review closure requests."}, status=status.HTTP_403_FORBIDDEN)
            decision = request.data.get("decision")
            if decision not in {"approve", "reject"}:
                return Response({"detail": "Unknown closure review decision."}, status=status.HTTP_400_BAD_REQUEST)
            notes = request.data.get("notes", "")
            if decision == "reject" and not notes:
                return Response({"detail": "Rejection reason is required."}, status=status.HTTP_400_BAD_REQUEST)
            if decision == "approve":
                alert.internal_status = "Closed"
                alert.status = Alert.Status.CLOSED
                alert.closed_at = timezone.now()
                add_timeline("Closure approved", notes or alert.closure_reason)
                resolve_notifications("alert", alert.reference, "closure-requested")
                reviewer_name = request.user.get_full_name() or request.user.username
                notify_users(
                    [alert.assigned_intake_officer] if alert.assigned_intake_officer_id else [],
                    title="Closure approved",
                    message=f"Your case closure request has been approved by {reviewer_name}. Case {alert.reference} has been successfully closed.",
                    category="Closure",
                    priority="warning",
                    target_type="alert",
                    target_id=alert.reference,
                    action_label="View resolved case",
                    route="resolved-cases",
                    dedupe_key=f"alert:{alert.id}:closure-approved",
                )
            else:
                alert.internal_status = "Investigation"
                alert.status = Alert.Status.ALLOCATED
                alert.escalation_notes = notes
                add_timeline("Closure rejected", notes)
                resolve_notifications("alert", alert.reference, "closure-requested")
                notify_users(
                    [alert.assigned_intake_officer] if alert.assigned_intake_officer_id else [],
                    title="Closure rejected",
                    message=f"{alert.reference} closure was rejected. Reason: {notes}",
                    category="Closure",
                    priority="warning",
                    target_type="alert",
                    target_id=alert.reference,
                    action_label="Continue case work",
                    route="triage",
                    dedupe_key=f"alert:{alert.id}:closure-rejected:{timezone.now().isoformat()}",
                )
        else:
            return Response({"detail": "Unknown case workflow action."}, status=status.HTTP_400_BAD_REQUEST)

        alert.save()
        audit(request.user, f"Case workflow action: {action_type}", alert)
        return Response(AlertSerializer(alert, context={"request": request}).data)

    @action(detail=True, methods=["post"], url_path="respond-more-info")
    def respond_more_info(self, request, reference=None):
        alert = self.get_object()
        if not has_role(request.user, EXTERNAL_ROLES):
            return Response({"detail": "Only external reporters can respond here."}, status=status.HTTP_403_FORBIDDEN)
        info_request = alert.information_requests.filter(resolved=False).order_by("-created_at").first()
        if not info_request:
            return Response({"detail": "No open information request found."}, status=status.HTTP_400_BAD_REQUEST)
        info_request.response = request.data.get("response", "")
        info_request.resolved = True
        info_request.responded_at = timezone.now()
        info_request.save()
        alert.status = Alert.Status.UNDER_REVIEW
        alert.internal_status = "Under Review"
        alert.save()
        audit(request.user, "More information submitted", alert)
        return Response(AlertSerializer(alert, context={"request": request}).data)

class IntakeViewSet(viewsets.ModelViewSet):
    serializer_class = IntakeSerializer
    queryset = Intake.objects.select_related("alert", "allocated_officer", "allocated_by", "reviewed_by", "created_by").all()

    def get_queryset(self):
        user = self.request.user
        qs = self.queryset
        if has_role(user, NATIONAL_ROLES):
            return qs
        if has_role(user, DISTRICT_CASE_ROLES):
            return qs.filter(Q(alert__district=user.profile.district) | Q(alert__isnull=True, created_by=user)) if user.profile.district_id else qs.filter(alert__isnull=True, created_by=user)
        if has_role(user, PROVINCIAL_ROLES):
            return qs.filter(Q(alert__district__province=user.profile.province) | Q(alert__isnull=True, created_by=user)) if user.profile.province_id else qs.filter(alert__isnull=True, created_by=user)
        return qs.none()

    def perform_create(self, serializer):
        source = self.request.data.get("intake_source") or "WALK_IN"
        district = getattr(getattr(self.request.user, "profile", None), "district", None)
        try:
            reference = next_case_reference(district)
        except ValueError as error:
            raise ValidationError({"detail": str(error)})
        intake = serializer.save(
            created_by=self.request.user,
            temporary_case_reference=reference,
            intake_source=source,
        )
        if intake.latitude is not None and intake.longitude is not None:
            mismatch = gps_location_mismatch(district.name if district else "", intake.latitude, intake.longitude)
            if mismatch != intake.location_mismatch:
                intake.location_mismatch = mismatch
                intake.save(update_fields=["location_mismatch"])

    @action(detail=True, methods=["post"])
    def screen(self, request, pk=None):
        intake = self.get_object()
        if not has_role(request.user, DISTRICT_CASE_ROLES | {UserProfile.Role.SYS_ADMIN}):
            return Response({"detail": "You do not have permission to screen intakes."}, status=status.HTTP_403_FORBIDDEN)
        if intake.alert:
            similar = Alert.objects.filter(
                district=intake.alert.district,
                child_first_name__iexact=intake.alert.child_first_name,
            ).exclude(id=intake.alert_id)
            intake.duplicate_result = "Potential duplicate review required" if intake.alert.child_first_name and similar.exists() else "No exact duplicate found"
        else:
            intake.duplicate_result = "No originating alert; manual duplicate review required"
        intake.initial_screening_notes = request.data.get("initial_screening_notes", intake.initial_screening_notes)
        intake.case_category = request.data.get("case_category", intake.case_category)
        intake.risk_level = request.data.get("risk_level", intake.risk_level)
        intake.immediate_action_required = request.data.get("immediate_action_required", intake.immediate_action_required)
        intake.immediate_action_plan = request.data.get("immediate_action_plan", intake.immediate_action_plan)
        if not intake.screening_completed_at:
            intake.screening_completed_at = timezone.now()
        intake.status = Intake.Status.SUPERVISOR_REVIEW
        intake.save()
        if intake.alert:
            intake.alert.status = Alert.Status.SUPERVISOR_REVIEW
            intake.alert.internal_status = "In Progress"
            intake.alert.save()
        audit(request.user, "Initial screening submitted", intake)
        notify_intake_submitted(intake)
        return Response(IntakeSerializer(intake, context={"request": request}).data)

    @action(detail=True, methods=["post"], url_path="supervisor-review")
    def supervisor_review(self, request, pk=None):
        intake = self.get_object()
        if not has_role(request.user, SUPERVISOR_ROLES):
            return Response({"detail": "Only supervisors can review intakes."}, status=status.HTTP_403_FORBIDDEN)
        decision = request.data.get("decision")
        intake.supervisor_notes = request.data.get("supervisor_notes", intake.supervisor_notes)
        intake.reviewed_by = request.user
        intake.reviewed_at = timezone.now()
        if decision == "approve":
            intake.status = Intake.Status.APPROVED
            if intake.alert:
                intake.alert.status = Alert.Status.APPROVED_ALLOCATION
                intake.alert.internal_status = "In Progress"
        elif decision == "return":
            intake.status = Intake.Status.RETURNED
            if intake.alert:
                intake.alert.status = Alert.Status.UNDER_REVIEW
                intake.alert.internal_status = "In Progress"
        elif decision == "approve_emergency":
            intake.immediate_action_required = True
            intake.status = Intake.Status.APPROVED
            if intake.alert:
                intake.alert.status = Alert.Status.EMERGENCY
                intake.alert.internal_status = "Escalated"
                intake.alert.emergency = True
        else:
            return Response({"detail": "Unknown supervisor decision."}, status=status.HTTP_400_BAD_REQUEST)
        intake.save()
        if intake.alert:
            intake.alert.save()
        resolve_notifications("case", intake.id, "submitted-review")
        if decision in {"approve", "approve_emergency"}:
            notify_intake_ready_for_allocation(intake)
        review_delay_seconds = None
        if intake.screening_completed_at and intake.reviewed_at:
            review_delay_seconds = max(0, int((intake.reviewed_at - intake.screening_completed_at).total_seconds()))
        audit(request.user, f"Supervisor decision: {decision}", intake, {
            "screening_completed_at": intake.screening_completed_at.isoformat() if intake.screening_completed_at else "",
            "reviewed_at": intake.reviewed_at.isoformat() if intake.reviewed_at else "",
            "review_delay_seconds": review_delay_seconds,
        })
        return Response(IntakeSerializer(intake, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def allocate(self, request, pk=None):
        intake = self.get_object()
        if not has_role(request.user, SUPERVISOR_ROLES):
            return Response({"detail": "Only supervisors can allocate cases."}, status=status.HTTP_403_FORBIDDEN)
        officer = User.objects.filter(id=request.data.get("officer_id"), profile__role=UserProfile.Role.DSDO).first()
        if not officer:
            return Response({"detail": "Select a valid case officer."}, status=status.HTTP_400_BAD_REQUEST)
        intake.allocated_officer = officer
        intake.allocated_by = request.user
        intake.allocated_at = timezone.now()
        intake.status = Intake.Status.ALLOCATED
        intake.save()
        if intake.alert:
            intake.alert.status = Alert.Status.ALLOCATED
            intake.alert.internal_status = "Assigned"
            intake.alert.save()
        resolve_notifications("case", intake.id, "ready-allocation")
        notify_case_allocated(intake)
        allocation_delay_seconds = None
        if intake.screening_completed_at and intake.allocated_at:
            allocation_delay_seconds = max(0, int((intake.allocated_at - intake.screening_completed_at).total_seconds()))
        audit(request.user, "Case allocated", intake, {
            "officer": officer.username,
            "screening_completed_at": intake.screening_completed_at.isoformat() if intake.screening_completed_at else "",
            "allocated_at": intake.allocated_at.isoformat() if intake.allocated_at else "",
            "allocation_delay_seconds": allocation_delay_seconds,
        })
        return Response(IntakeSerializer(intake, context={"request": request}).data)

    @action(detail=True, methods=["post"], url_path="complete-assessment")
    def complete_assessment(self, request, pk=None):
        intake = self.get_object()
        if not intake.allocated_at or not intake.allocated_officer_id:
            return Response({"detail": "Assessment timer starts only after case allocation."}, status=status.HTTP_400_BAD_REQUEST)
        if not (request.user == intake.allocated_officer or has_role(request.user, SUPERVISOR_ROLES)):
            return Response({"detail": "Only the allocated officer or a supervisor can complete the assessment."}, status=status.HTTP_403_FORBIDDEN)
        completed_at = timezone.now()
        intake.assessment_completed_at = completed_at
        intake.assessment_completed_by = request.user
        intake.save(update_fields=["assessment_completed_at", "assessment_completed_by", "updated_at"])
        due_at = intake.allocated_at + timedelta(days=7)
        remaining_seconds = int((due_at - completed_at).total_seconds())
        audit(request.user, "Assessment completed", intake, {
            "assessment_started_at": intake.allocated_at.isoformat(),
            "assessment_due_at": due_at.isoformat(),
            "remaining_seconds": remaining_seconds,
        })
        return Response(IntakeSerializer(intake, context={"request": request}).data)

    @action(detail=True, methods=["post"], url_path="submit-assessment-care-plan")
    def submit_assessment_care_plan(self, request, pk=None):
        intake = self.get_object()
        if not intake.allocated_at or not intake.allocated_officer_id:
            return Response({"detail": "Assessment and care plan can only be submitted after allocation."}, status=status.HTTP_400_BAD_REQUEST)
        if request.user != intake.allocated_officer and not has_role(request.user, SUPERVISOR_ROLES):
            return Response({"detail": "Only the allocated officer can submit the assessment and care plan."}, status=status.HTTP_403_FORBIDDEN)
        assessment = clean_assessment_draft(request.data.get("assessment") or {})
        care_plan = clean_care_plan_draft(request.data.get("care_plan") or {})
        care_plan_versions = request.data.get("care_plan_versions") or []
        care_plan_change_logs = request.data.get("care_plan_change_logs") or []
        case_conferences = request.data.get("case_conferences") or []
        justice = request.data.get("justice") or {}
        referrals = request.data.get("referrals") or []
        service_tracking = request.data.get("service_tracking") or []
        case_notes = request.data.get("case_notes") or []
        case_documents = request.data.get("case_documents") or []
        monitoring_followups = request.data.get("monitoring_followups") or []
        if not assessment:
            return Response({"detail": "Assessment is required before the care plan can be submitted."}, status=status.HTTP_400_BAD_REQUEST)
        if not care_plan.get("items"):
            return Response({"detail": "Care plan is required for combined submission."}, status=status.HTTP_400_BAD_REQUEST)
        now = timezone.now()
        intake.assessment_draft = assessment
        intake.care_plan_draft = care_plan
        intake.care_plan_versions_draft = care_plan_versions
        intake.care_plan_change_logs_draft = care_plan_change_logs
        intake.case_conferences_draft = case_conferences
        intake.justice_draft = justice
        intake.referrals_draft = referrals
        intake.service_tracking_draft = service_tracking
        intake.case_notes_draft = case_notes
        intake.case_documents_draft = case_documents
        intake.monitoring_followups_draft = monitoring_followups
        intake.case_reviews_draft = request.data.get("case_reviews", intake.case_reviews_draft or [])
        intake.assessment_completed_at = intake.assessment_completed_at or now
        intake.assessment_completed_by = intake.assessment_completed_by or request.user
        intake.assessment_care_plan_status = "Submitted"
        intake.assessment_care_plan_submitted_at = now
        intake.assessment_care_plan_submitted_by = request.user
        intake.save()
        audit(request.user, "Assessment and care plan submitted", intake)
        notify_assessment_care_plan_submitted(intake)
        return Response(IntakeSerializer(intake, context={"request": request}).data)

    @action(detail=True, methods=["post"], url_path="save-execution-draft")
    def save_execution_draft(self, request, pk=None):
        intake = self.get_object()
        if not intake.allocated_at or not intake.allocated_officer_id:
            return Response({"detail": "Case execution drafts can only be saved after allocation."}, status=status.HTTP_400_BAD_REQUEST)
        if request.user != intake.allocated_officer and not has_role(request.user, SUPERVISOR_ROLES):
            return Response({"detail": "Only the allocated officer or a supervisor can save this case draft."}, status=status.HTTP_403_FORBIDDEN)

        intake.assessment_draft = clean_assessment_draft(request.data.get("assessment", intake.assessment_draft or {}))
        intake.care_plan_draft = clean_care_plan_draft(request.data.get("care_plan", intake.care_plan_draft or {}))
        intake.care_plan_versions_draft = request.data.get("care_plan_versions", intake.care_plan_versions_draft or [])
        intake.care_plan_change_logs_draft = request.data.get("care_plan_change_logs", intake.care_plan_change_logs_draft or [])
        intake.case_conferences_draft = request.data.get("case_conferences", intake.case_conferences_draft or [])
        intake.justice_draft = request.data.get("justice", intake.justice_draft or {})
        intake.referrals_draft = request.data.get("referrals", intake.referrals_draft or [])
        intake.service_tracking_draft = request.data.get("service_tracking", intake.service_tracking_draft or [])
        intake.case_notes_draft = request.data.get("case_notes", intake.case_notes_draft or [])
        intake.case_documents_draft = request.data.get("case_documents", intake.case_documents_draft or [])
        intake.monitoring_followups_draft = request.data.get("monitoring_followups", intake.monitoring_followups_draft or [])
        intake.case_reviews_draft = request.data.get("case_reviews", intake.case_reviews_draft or [])
        if intake.assessment_care_plan_status in {"", "Submitted"}:
            intake.assessment_care_plan_status = "Draft"
        intake.save()
        audit(request.user, "Case execution draft saved", intake)
        return Response(IntakeSerializer(intake, context={"request": request}).data)

    @action(detail=True, methods=["get"], url_path=r"referrals/(?P<referral_index>\d+)/pdf")
    def referral_pdf(self, request, pk=None, referral_index=None):
        from weasyprint import HTML

        intake = self.get_object()
        referrals = intake.referrals_draft if isinstance(intake.referrals_draft, list) else []
        index = int(referral_index)
        if index < 0 or index >= len(referrals) or not isinstance(referrals[index], dict):
            return Response({"detail": "Referral record not found."}, status=status.HTTP_404_NOT_FOUND)

        referral = referrals[index]
        pdf = HTML(string=build_referral_pdf_html(intake, referral, index, request.user)).write_pdf()
        filename = f"referral-{intake.temporary_case_reference}-{index + 1}.pdf".replace("/", "-")
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    @action(detail=True, methods=["post"], url_path="review-assessment-care-plan")
    def review_assessment_care_plan(self, request, pk=None):
        intake = self.get_object()
        if not has_role(request.user, SUPERVISOR_ROLES):
            return Response({"detail": "Only supervisors can review assessment and care plan submissions."}, status=status.HTTP_403_FORBIDDEN)
        decision = request.data.get("decision")
        if decision not in {"approve", "request_revision", "approve_with_comments"}:
            return Response({"detail": "Unknown assessment and care plan decision."}, status=status.HTTP_400_BAD_REQUEST)
        intake.assessment_care_plan_status = {
            "approve": "Approved",
            "approve_with_comments": "Approved with Comments",
            "request_revision": "Revision Requested",
        }[decision]
        intake.assessment_care_plan_review_notes = request.data.get("notes", "")
        intake.assessment_care_plan_reviewed_at = timezone.now()
        intake.assessment_care_plan_reviewed_by = request.user
        intake.save()
        audit(request.user, f"Assessment and care plan review: {decision}", intake, {"notes": intake.assessment_care_plan_review_notes})
        resolve_notifications("case", intake.id, "assessment-care-plan-submitted")
        return Response(IntakeSerializer(intake, context={"request": request}).data)

    @action(detail=True, methods=["post"], url_path="supervisor-case-review")
    def supervisor_case_review(self, request, pk=None):
        intake = self.get_object()
        if request.user != intake.allocated_officer and not has_role(request.user, SUPERVISOR_ROLES):
            return Response({"detail": "Only the allocated officer or supervisor can record case reviews."}, status=status.HTTP_403_FORBIDDEN)
        decision = request.data.get("decision", "Continue Current Plan")
        case_reviews = request.data.get("case_reviews")
        if isinstance(case_reviews, list):
            intake.case_reviews_draft = case_reviews
        intake.last_case_review_decision = decision
        intake.last_case_review_notes = request.data.get("notes", "")
        intake.last_case_review_at = timezone.now()
        intake.last_case_review_by = request.user
        intake.save()
        audit(request.user, "Supervisor case review recorded", intake, {"decision": decision, "notes": intake.last_case_review_notes})
        return Response(IntakeSerializer(intake, context={"request": request}).data)

    @action(detail=True, methods=["post"], url_path="request-closure")
    def request_closure(self, request, pk=None):
        intake = self.get_object()
        if request.user != intake.allocated_officer and not has_role(request.user, SUPERVISOR_ROLES):
            return Response({"detail": "Only the allocated officer or supervisor can request closure."}, status=status.HTTP_403_FORBIDDEN)
        intake.closure_status = "Requested"
        closure_payload = request.data.get("closure") or {}
        closure_history = request.data.get("closure_history")
        intake.closure_draft = closure_payload
        if isinstance(closure_history, list):
            intake.closure_history_draft = closure_history
        intake.closure_review_notes = request.data.get("notes", "") or closure_payload.get("currentSituation", "") or closure_payload.get("closureSummary", "")
        intake.closure_requested_at = timezone.now()
        intake.closure_requested_by = request.user
        intake.save()
        audit(request.user, "Closure requested", intake, {"notes": intake.closure_review_notes})
        district = intake.alert.district if intake.alert_id else getattr(intake.created_by.profile, "district", None)
        notify_users(
            notification_recipients([UserProfile.Role.DISTRICT_HEAD], district=district, exclude_user=request.user),
            title="Closure request submitted",
            message=f"{intake_case_reference(intake)} has a closure request waiting for supervisor review.",
            category="Care Plan",
            priority="warning",
            target_type="case",
            target_id=intake.id,
            action_label="Review closure",
            route="allocated-cases",
            dedupe_key=f"intake:{intake.id}:closure-requested",
        )
        return Response(IntakeSerializer(intake, context={"request": request}).data)

    @action(detail=True, methods=["post"], url_path="review-closure")
    def review_closure(self, request, pk=None):
        intake = self.get_object()
        if not has_role(request.user, SUPERVISOR_ROLES):
            return Response({"detail": "Only supervisors can review closure requests."}, status=status.HTTP_403_FORBIDDEN)
        decision = request.data.get("decision")
        if decision not in {"approve", "reject"}:
            return Response({"detail": "Unknown closure decision."}, status=status.HTTP_400_BAD_REQUEST)
        intake.closure_status = "Approved" if decision == "approve" else "Rejected"
        if intake.closure_history_draft:
            latest = dict(intake.closure_history_draft[-1])
            latest["decision"] = "Approved" if decision == "approve" else "Rejected"
            latest["status"] = intake.closure_status
            latest["approvedBy"] = request.user.get_full_name() or request.user.username
            latest["approvedAt"] = timezone.now().isoformat()
            latest["supervisorReason"] = request.data.get("notes", "")
            intake.closure_history_draft = [*intake.closure_history_draft[:-1], latest]
        intake.closure_review_notes = request.data.get("notes", "")
        intake.closure_reviewed_at = timezone.now()
        intake.closure_reviewed_by = request.user
        intake.save()
        audit(request.user, f"Closure {decision}", intake, {"notes": intake.closure_review_notes})
        resolve_notifications("case", intake.id, "closure-requested")
        reviewer_name = request.user.get_full_name() or request.user.username
        requester = intake.closure_requested_by or intake.allocated_officer
        if requester and requester != request.user:
            case_reference = intake_case_reference(intake)
            approved = decision == "approve"
            notify_users(
                [requester],
                title="Closure approved" if approved else "Closure rejected",
                message=(
                    f"Your case closure request has been approved by {reviewer_name}. Case {case_reference} has been successfully closed."
                    if approved
                    else f"Your case closure request has been rejected by {reviewer_name}. Case {case_reference} requires more work. Reason: {intake.closure_review_notes or 'No reason captured.'}"
                ),
                category="Closure",
                priority="warning",
                target_type="case",
                target_id=intake.id,
                action_label="View resolved case" if approved else "Continue case work",
                route="resolved-cases" if approved else "allocated-cases",
                dedupe_key=f"intake:{intake.id}:closure-{decision}:{intake.closure_reviewed_at.isoformat()}",
            )
        return Response(IntakeSerializer(intake, context={"request": request}).data)


def set_json_path(payload, path, value):
    if not path or value in (None, ""):
        return payload
    parts = path.split(".")
    cursor = payload
    for part in parts[:-1]:
        cursor = cursor.setdefault(part, {})
    try:
        parsed_value = json.loads(value) if isinstance(value, str) and value.strip().startswith(("{", "[")) else value
    except json.JSONDecodeError:
        parsed_value = value
    cursor[parts[-1]] = parsed_value
    return payload


def apply_intake_update_request(update_request):
    intake = update_request.intake
    changed = []
    direct_fields = {"case_category", "risk_level", "immediate_action_plan", "initial_screening_notes", "prior_assistance"}
    for field in update_request.requested_fields:
        path = field.get("path")
        proposed = field.get("proposed_value", field.get("new_value"))
        if not path or proposed in (None, ""):
            continue
        root = path.split(".")[0]
        if root in direct_fields and "." not in path:
            current_value = getattr(intake, root)
            setattr(intake, root, proposed)
            changed.append({
                "path": path,
                "label": field.get("label"),
                "from": field.get("current_value", field.get("old_value", current_value)),
                "to": proposed,
                "tab": field.get("tab_name") or update_request.tab,
                "section": field.get("section_name") or update_request.tab,
            })
            continue
        if root not in {"opening_summary", "child_profile_draft", "household_profile_draft", "background_information"}:
            continue
        current = deepcopy(getattr(intake, root) or {})
        set_json_path(current, ".".join(path.split(".")[1:]), proposed)
        setattr(intake, root, current)
        changed.append({
            "path": path,
            "label": field.get("label"),
            "from": field.get("current_value", field.get("old_value", "")),
            "to": proposed,
            "tab": field.get("tab_name") or update_request.tab,
            "section": field.get("section_name") or update_request.tab,
        })
    if changed:
        intake.save()
    return changed


class UpdateRequestViewSet(viewsets.ModelViewSet):
    serializer_class = UpdateRequestSerializer
    queryset = UpdateRequest.objects.select_related("intake", "requested_by", "reviewed_by").all()

    def get_queryset(self):
        user = self.request.user
        qs = self.queryset
        if has_role(user, NATIONAL_ROLES):
            return qs
        if has_role(user, PROVINCIAL_ROLES):
            return qs.filter(intake__created_by__profile__province=user.profile.province)
        if has_role(user, {UserProfile.Role.DISTRICT_HEAD}):
            return qs.filter(intake__created_by__profile__district=user.profile.district)
        if has_role(user, {UserProfile.Role.DSDO}):
            return qs.filter(Q(requested_by=user) | Q(intake__allocated_officer=user))
        return qs.none()

    def perform_create(self, serializer):
        update_request = serializer.save(requested_by=self.request.user)
        audit(self.request.user, "Intake update requested", update_request.intake, {
            "update_request_id": update_request.id,
            "tab": update_request.tab,
            "fields": update_request.requested_fields,
            "reason": update_request.reason,
        })
        intake = update_request.intake
        district = intake.alert.district if intake.alert_id else getattr(intake.created_by.profile, "district", None)
        notify_users(
            notification_recipients([UserProfile.Role.DISTRICT_HEAD], district=district, exclude_user=self.request.user),
            title="Intake update request submitted",
            message=f"{intake_case_reference(intake)} has an update request for {update_request.tab}.",
            category="Intake",
            priority="warning",
            target_type="case",
            target_id=intake.id,
            action_label="Review request",
            route="update-requests",
            dedupe_key=f"update-request:{update_request.id}:submitted",
        )

    @action(detail=True, methods=["post"])
    def review(self, request, pk=None):
        update_request = self.get_object()
        if not has_role(request.user, SUPERVISOR_ROLES):
            return Response({"detail": "Only supervisors can review update requests."}, status=status.HTTP_403_FORBIDDEN)
        if update_request.status != UpdateRequest.Status.PENDING:
            return Response({"detail": "This update request has already been reviewed."}, status=status.HTTP_400_BAD_REQUEST)
        decision = request.data.get("decision")
        update_request.review_notes = request.data.get("review_notes", update_request.review_notes)
        update_request.reviewed_by = request.user
        update_request.reviewed_at = timezone.now()
        if decision == "approve":
            changed = apply_intake_update_request(update_request)
            update_request.status = UpdateRequest.Status.APPROVED
            action = "Intake update approved"
        elif decision == "reject":
            changed = []
            update_request.status = UpdateRequest.Status.REJECTED
            action = "Intake update rejected"
        else:
            return Response({"detail": "Unknown review decision."}, status=status.HTTP_400_BAD_REQUEST)
        update_request.save()
        audit(request.user, action, update_request.intake, {
            "update_request_id": update_request.id,
            "tab": update_request.tab,
            "changed": changed,
            "review_notes": update_request.review_notes,
        })
        resolve_notifications("case", update_request.intake_id, f"update-request:{update_request.id}")
        return Response(UpdateRequestSerializer(update_request, context={"request": request}).data)


class MoreInformationRequestViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = MoreInformationRequestSerializer
    queryset = MoreInformationRequest.objects.select_related("alert", "requested_by").all()

    def get_queryset(self):
        user = self.request.user
        qs = self.queryset
        if has_role(user, EXTERNAL_ROLES):
            return qs.filter(alert__reporter=user)
        if has_role(user, INTERNAL_ROLES):
            return qs
        return qs.none()


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = NotificationSerializer
    queryset = Notification.objects.select_related("recipient").all()

    def get_queryset(self):
        qs = self.queryset.filter(recipient=self.request.user)
        if getattr(self, "action", "") == "mark_read":
            return qs
        filter_value = self.request.query_params.get("status", "active")
        if filter_value == "all":
            return qs
        if filter_value == "resolved":
            return qs.filter(resolved_at__isnull=False)
        qs = qs.filter(resolved_at__isnull=True)
        if filter_value == "unread":
            return qs.filter(read_at__isnull=True)
        if filter_value == "read":
            return qs.filter(read_at__isnull=False)
        return qs

    @action(detail=True, methods=["post"], url_path="mark-read")
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        if not notification.read_at:
            notification.read_at = timezone.now()
            notification.save(update_fields=["read_at", "updated_at"])
        return Response(NotificationSerializer(notification, context={"request": request}).data)

    @action(detail=False, methods=["post"], url_path="mark-all-read")
    def mark_all_read(self, request):
        self.get_queryset().filter(read_at__isnull=True).update(read_at=timezone.now())
        return Response({"updated": True})


class NotificationRuleViewSet(viewsets.ModelViewSet):
    serializer_class = NotificationRuleSerializer
    queryset = NotificationRule.objects.all()

    def get_queryset(self):
        if has_role(self.request.user, NATIONAL_ROLES):
            return self.queryset
        return self.queryset.filter(enabled=True)

    def create(self, request, *args, **kwargs):
        if not has_role(request.user, NATIONAL_ROLES):
            return Response({"detail": "Only national administrators can create notification rules."}, status=status.HTTP_403_FORBIDDEN)
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        if not has_role(request.user, NATIONAL_ROLES):
            return Response({"detail": "Only national administrators can update notification rules."}, status=status.HTTP_403_FORBIDDEN)
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        if not has_role(request.user, NATIONAL_ROLES):
            return Response({"detail": "Only national administrators can delete notification rules."}, status=status.HTTP_403_FORBIDDEN)
        return super().destroy(request, *args, **kwargs)


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AuditLogSerializer
    queryset = AuditLog.objects.select_related("actor", "actor__profile", "actor__profile__province", "actor__profile__district").all()

    def get_queryset(self):
        if has_role(self.request.user, {UserProfile.Role.SYS_ADMIN}):
            return self.queryset
        return AuditLog.objects.none()


class CalendarTaskViewSet(viewsets.ModelViewSet):
    serializer_class = CalendarTaskSerializer
    queryset = CalendarTask.objects.select_related("created_by").all()

    def get_queryset(self):
        user = self.request.user
        if has_role(user, INTERNAL_ROLES):
            return self.queryset
        return self.queryset.filter(created_by=user)
