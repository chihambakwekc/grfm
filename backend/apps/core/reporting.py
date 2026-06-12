from collections import Counter
from datetime import timedelta
from django.db.models import Count, Q
from django.db.models.functions import TruncMonth
from django.utils import timezone

from .models import Alert, UserProfile

NATIONAL_ROLES = {
    UserProfile.Role.SYS_ADMIN,
    UserProfile.Role.NATIONAL,
    UserProfile.Role.NATIONAL_PROGRAM,
}
PROVINCIAL_ROLES = {UserProfile.Role.PROVINCIAL_HEAD}
DISTRICT_CASE_ROLES = {UserProfile.Role.DISTRICT_HEAD, UserProfile.Role.DSDO}


def has_role(user, roles):
    return user.is_authenticated and hasattr(user, "profile") and user.profile.active and user.profile.role in roles


def scoped_alerts(user):
    qs = Alert.objects.select_related("district", "district__province", "ward", "reporter", "reporter__profile")
    if has_role(user, NATIONAL_ROLES):
        return qs
    if has_role(user, PROVINCIAL_ROLES):
        return qs.filter(district__province=user.profile.province) if user.profile.province_id else qs.none()
    if has_role(user, DISTRICT_CASE_ROLES):
        return qs.filter(district=user.profile.district) if user.profile.district_id else qs.none()
    if has_role(user, {UserProfile.Role.COMMUNITY_USER, UserProfile.Role.CCW, UserProfile.Role.NGO, UserProfile.Role.POLICE, UserProfile.Role.TEACHER, UserProfile.Role.NURSE}):
        return qs.filter(reporter=user)
    return qs.none()


def apply_date_range(qs, start=None, end=None, field="created_at"):
    if start:
        qs = qs.filter(**{f"{field}__date__gte": start})
    if end:
        qs = qs.filter(**{f"{field}__date__lte": end})
    return qs


def rows_by_count(qs, field, label="name"):
    rows = qs.values(field).annotate(value=Count("id")).order_by("-value")
    return [{"name": row[field] or "Not captured", "value": row["value"]} for row in rows]


def monthly_alert_trend(alerts):
    rows = alerts.annotate(month=TruncMonth("created_at")).values("month").annotate(value=Count("id")).order_by("month")
    return [{"month": row["month"].strftime("%Y-%m") if row["month"] else "Unknown", "value": row["value"]} for row in rows]


def concern_distribution(alerts):
    counts = Counter()
    for categories in alerts.values_list("concern_categories", flat=True):
        if categories:
            counts.update(categories)
        else:
            counts["Uncategorized"] += 1
    return [{"name": name, "value": value} for name, value in counts.most_common()]


def seconds_between(start, end):
    if not start or not end:
        return None
    return max(0, int((end - start).total_seconds()))


def average(values):
    clean = [value for value in values if value is not None]
    return round(sum(clean) / len(clean)) if clean else None


def format_duration(seconds):
    if seconds is None:
        return "-"
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if not days and minutes:
        parts.append(f"{minutes}m")
    return " ".join(parts) or "0m"


def apply_report_filters(alerts, province=None, district=None, programme=None, case_type=None, priority=None, status=None):
    if province and province != "All Provinces":
        alerts = alerts.filter(district__province__name=province)
    if district and district != "All Districts":
        alerts = alerts.filter(district__name=district)
    if programme and programme != "All Programmes":
        alerts = alerts.filter(Q(programme__icontains=programme) | Q(concern_categories__icontains=programme))
    if case_type and case_type not in {"All Case Types", "All Submission Types"}:
        token = case_type.replace(" Cases", "").replace(" Reports", "").replace(" Submissions", "")
        if case_type in {"Open Cases", "Open Submissions"}:
            alerts = alerts.exclude(Q(status__icontains="Closed") | Q(status__icontains="Rejected") | Q(status__icontains="Duplicate"))
        elif case_type in {"Closed Cases", "Closed Submissions"}:
            alerts = alerts.filter(Q(status__icontains="Closed") | Q(status__icontains="Rejected") | Q(status__icontains="Duplicate"))
        else:
            alerts = alerts.filter(Q(concern_categories__icontains=token) | Q(reporting_channel__icontains=token))
    if priority and priority != "All Priorities":
        alerts = alerts.filter(priority__iexact=priority)
    if status and status != "All Statuses":
        alerts = alerts.filter(Q(status__iexact=status) | Q(internal_status__iexact=status))
    return alerts


def open_case_q():
    return ~Q(internal_status__in=["Resolved", "Closed"]) & ~Q(status__icontains="Closed") & ~Q(status__icontains="Rejected") & ~Q(status__icontains="Duplicate")


def closed_case_q():
    return Q(internal_status="Closed") | Q(status__icontains="Closed")


def overdue_case_q(now=None):
    now = now or timezone.now()
    return open_case_q() & Q(created_at__lt=now - timedelta(days=14))


def submission_type_q(label):
    text = (label or "").lower()
    if "abuse" in text or "protection" in text:
        return Q(concern_categories__icontains="Abuse") | Q(concern_categories__icontains="Protection")
    if "feedback" in text:
        return Q(reporting_channel__icontains="Feedback") | Q(concern_categories__icontains="Feedback")
    if "voice" in text:
        return Q(reporting_channel__icontains="Voice")
    return Q()


def priority_q(*values):
    query = Q()
    for value in values:
        query |= Q(priority__iexact=value)
    return query


def programme_name_expr(row):
    return row.get("programme") or "Uncategorized"


def avg_days_from_rows(rows):
    values = []
    for created_at, closed_at, resolved_at, assigned_at in rows:
        end = closed_at or resolved_at or assigned_at
        seconds = seconds_between(created_at, end)
        if seconds is not None:
            values.append(seconds / 86400)
    return round(sum(values) / len(values), 1) if values else 0


def report_scope_label(user, province=None, district=None):
    profile = getattr(user, "profile", None)
    if district and district != "All Districts":
        return district
    if province and province != "All Provinces":
        return province
    if profile and profile.district_id:
        return profile.district.name
    if profile and profile.province_id:
        return profile.province.name
    return "National"


def build_grfm_summary(alerts, user, now):
    total = alerts.count()
    return {
        "summary": {
            "Total Submissions": total,
            "Complaints": alerts.exclude(submission_type_q("abuse") | submission_type_q("feedback") | submission_type_q("voice")).count(),
            "Abuse Reports": alerts.filter(submission_type_q("abuse")).count(),
            "Feedback": alerts.filter(submission_type_q("feedback")).count(),
            "Voice Reports": alerts.filter(submission_type_q("voice")).count(),
            "Open Cases": alerts.filter(open_case_q()).count(),
            "Closed Cases": alerts.filter(closed_case_q()).count(),
            "Pending Cases": alerts.filter(internal_status__in=["New", "Assigned", "Investigation", "Awaiting Referral Response", "Escalated"]).count(),
            "Overdue Cases": alerts.filter(overdue_case_q(now)).count(),
        },
        "tables": {
            "breakdown": [
                {"Area": row["district__name"] or "Not captured", "Total": row["total"], "Open": row["open"], "Closed": row["closed"], "Overdue": row["overdue"]}
                for row in alerts.values("district__name").annotate(
                    total=Count("id"),
                    open=Count("id", filter=open_case_q()),
                    closed=Count("id", filter=closed_case_q()),
                    overdue=Count("id", filter=overdue_case_q(now)),
                ).order_by("district__name")
            ],
            "provinceComparison": [
                {"Province": row["district__province__name"] or "Not captured", "Total": row["total"], "Open": row["open"], "Closed": row["closed"], "Overdue": row["overdue"]}
                for row in alerts.values("district__province__name").annotate(
                    total=Count("id"),
                    open=Count("id", filter=open_case_q()),
                    closed=Count("id", filter=closed_case_q()),
                    overdue=Count("id", filter=overdue_case_q(now)),
                ).order_by("district__province__name")
            ],
        },
    }


def build_programme_performance(alerts):
    programme_rows = alerts.values("programme").annotate(
        total=Count("id"),
        open=Count("id", filter=open_case_q()),
        closed=Count("id", filter=closed_case_q()),
    ).order_by("programme")
    province_rows = alerts.values("district__province__name", "programme").annotate(total=Count("id")).order_by("district__province__name", "programme")
    matrix = {}
    for row in province_rows:
        province = row["district__province__name"] or "Not captured"
        matrix.setdefault(province, {"Province": province})
        matrix[province][programme_name_expr(row)] = row["total"]
    return {
        "summary": {
            "Programmes": len({programme_name_expr(row) for row in programme_rows}),
            "Total Cases": alerts.count(),
            "Open Cases": alerts.filter(open_case_q()).count(),
            "Closed Cases": alerts.filter(closed_case_q()).count(),
        },
        "tables": {
            "programmePerformance": [{"Programme": programme_name_expr(row), "Total": row["total"], "Open": row["open"], "Closed": row["closed"]} for row in programme_rows],
            "provinceProgrammeComparison": list(matrix.values()),
        },
    }


def build_abuse_protection(alerts):
    abuse_alerts = alerts.filter(submission_type_q("abuse"))
    category_counts = Counter()
    for categories in abuse_alerts.values_list("concern_categories", flat=True):
        if categories:
            category_counts.update(categories)
        else:
            category_counts["Uncategorized"] += 1
    return {
        "summary": {
            "Abuse Reports": abuse_alerts.count(),
            "Critical": abuse_alerts.filter(priority_q("Critical")).count(),
            "High": abuse_alerts.filter(priority_q("High")).count(),
            "Open": abuse_alerts.filter(open_case_q()).count(),
        },
        "tables": {
            "categories": [{"Category": name, "Cases": count} for name, count in category_counts.most_common()],
            "districtComparison": [{"District": row["district__name"] or "Not captured", "Cases": row["cases"]} for row in abuse_alerts.values("district__name").annotate(cases=Count("id")).order_by("-cases")],
            "provinceComparison": [{"Province": row["district__province__name"] or "Not captured", "Cases": row["cases"]} for row in abuse_alerts.values("district__province__name").annotate(cases=Count("id")).order_by("-cases")],
            "wardHotspots": [{"Ward": row["ward__name"] or "Not captured", "Cases": row["cases"]} for row in abuse_alerts.values("ward__name").annotate(cases=Count("id")).order_by("-cases")],
        },
    }


def build_sla_response(alerts, now):
    district_rows = []
    for district in alerts.values_list("district__name", flat=True).distinct():
        district_alerts = alerts.filter(district__name=district)
        avg_days = avg_days_from_rows(district_alerts.values_list("created_at", "closed_at", "resolved_at", "assigned_at"))
        district_rows.append({"District": district or "Not captured", "Avg Response": f"{avg_days} days", "Overdue": district_alerts.filter(overdue_case_q(now)).count()})
    province_rows = []
    for province in alerts.values_list("district__province__name", flat=True).distinct():
        province_alerts = alerts.filter(district__province__name=province)
        avg_days = avg_days_from_rows(province_alerts.values_list("created_at", "closed_at", "resolved_at", "assigned_at"))
        province_rows.append({"Province": province or "Not captured", "Avg Response": f"{avg_days} days", "Overdue": province_alerts.filter(overdue_case_q(now)).count()})
    return {
        "summary": {
            "Total Cases": alerts.count(),
            "Overdue Cases": alerts.filter(overdue_case_q(now)).count(),
            "Open Cases": alerts.filter(open_case_q()).count(),
            "Closed Cases": alerts.filter(closed_case_q()).count(),
        },
        "tables": {"districtSla": sorted(district_rows, key=lambda row: row["Overdue"], reverse=True), "provinceSla": sorted(province_rows, key=lambda row: row["Overdue"], reverse=True)},
    }


def build_officer_workload(alerts, now):
    officer_rows = []
    for row in alerts.values("assigned_intake_officer__first_name", "assigned_intake_officer__last_name", "assigned_intake_officer__username").annotate(
        open=Count("id", filter=open_case_q()),
        overdue=Count("id", filter=overdue_case_q(now)),
        total=Count("id"),
    ).order_by("-open"):
        name = " ".join(part for part in [row["assigned_intake_officer__first_name"], row["assigned_intake_officer__last_name"]] if part).strip() or row["assigned_intake_officer__username"] or "Unassigned"
        officer_rows.append({"Officer": name, "Open": row["open"], "Overdue": row["overdue"], "Total": row["total"]})
    return {
        "summary": {
            "Assigned Cases": alerts.exclude(assigned_intake_officer__isnull=True).count(),
            "Unassigned Cases": alerts.filter(assigned_intake_officer__isnull=True).count(),
            "Open Cases": alerts.filter(open_case_q()).count(),
            "Overdue Cases": alerts.filter(overdue_case_q(now)).count(),
        },
        "tables": {
            "officerWorkload": officer_rows,
            "districtWorkload": [{"District": row["district__name"] or "Not captured", "Cases": row["cases"], "Open": row["open"], "Overdue": row["overdue"]} for row in alerts.values("district__name").annotate(cases=Count("id"), open=Count("id", filter=open_case_q()), overdue=Count("id", filter=overdue_case_q(now))).order_by("-cases")],
            "provinceWorkload": [{"Province": row["district__province__name"] or "Not captured", "Cases": row["cases"], "Open": row["open"], "Overdue": row["overdue"]} for row in alerts.values("district__province__name").annotate(cases=Count("id"), open=Count("id", filter=open_case_q()), overdue=Count("id", filter=overdue_case_q(now))).order_by("-cases")],
        },
    }


def build_geographic_hotspots(alerts):
    return {
        "summary": {
            "Hotspot Areas": alerts.values("district__name").distinct().count(),
            "Complaints": alerts.exclude(submission_type_q("abuse") | submission_type_q("feedback") | submission_type_q("voice")).count(),
            "Abuse Reports": alerts.filter(submission_type_q("abuse")).count(),
            "Voice Reports": alerts.filter(submission_type_q("voice")).count(),
        },
        "tables": {
            "districtHotspots": [{"District": row["district__name"] or "Not captured", "Cases": row["cases"]} for row in alerts.values("district__name").annotate(cases=Count("id")).order_by("-cases")],
            "wardHotspots": [{"Ward": row["ward__name"] or "Not captured", "Cases": row["cases"]} for row in alerts.values("ward__name").annotate(cases=Count("id")).order_by("-cases")],
            "provinceHotspots": [{"Province": row["district__province__name"] or "Not captured", "Cases": row["cases"]} for row in alerts.values("district__province__name").annotate(cases=Count("id")).order_by("-cases")],
        },
    }


def build_report_payload(user, start=None, end=None, province=None, district=None, programme=None, case_type=None, priority=None, status=None, report_type=None):
    alerts = apply_date_range(scoped_alerts(user), start, end)
    alerts = apply_report_filters(alerts, province=province, district=district, programme=programme, case_type=case_type, priority=priority, status=status)
    now = timezone.now()
    closed_alerts = alerts.filter(Q(status__icontains="Closed") | Q(status__icontains="Rejected") | Q(status__icontains="Duplicate"))
    report_builders = {
        "GRFM Summary Report": lambda: build_grfm_summary(alerts, user, now),
        "Programme Performance Report": lambda: build_programme_performance(alerts),
        "Abuse & Protection Report": lambda: build_abuse_protection(alerts),
        "SLA & Response Time Report": lambda: build_sla_response(alerts, now),
        "Officer Workload Report": lambda: build_officer_workload(alerts, now),
        "Geographic Hotspot Report": lambda: build_geographic_hotspots(alerts),
    }
    specific_report = report_builders.get(report_type or "", lambda: None)()
    if specific_report:
        return {
            "generatedAt": now.isoformat(),
            "scope": report_scope_label(user, province=province, district=district),
            "reportType": report_type,
            "summary": specific_report["summary"],
            "charts": {
                "casesByProvince": rows_by_count(alerts, "district__province__name"),
                "casesByDistrict": rows_by_count(alerts, "district__name"),
                "caseStatus": rows_by_count(alerts, "internal_status"),
                "riskDistribution": rows_by_count(alerts, "priority"),
                "concernDistribution": concern_distribution(alerts),
                "monthlyTrend": monthly_alert_trend(alerts),
                "assessmentStatus": rows_by_count(alerts, "internal_status"),
                "funnel": [],
            },
            "tables": specific_report["tables"],
        }

    return {
        "generatedAt": now.isoformat(),
        "scope": report_scope_label(user, province=province, district=district),
        "summary": {
            "totalAlerts": alerts.count(),
            "totalIntakes": 0,
            "allocatedCases": 0,
            "highRiskAlerts": alerts.filter(Q(emergency=True) | Q(priority__in=["HIGH", "CRITICAL", "High", "Critical"])).count(),
            "overdueAssessments": 0,
            "completedAssessments": closed_alerts.count(),
            "averageAllocationDelaySeconds": None,
            "averageAllocationDelayLabel": "-",
        },
        "charts": {
            "casesByProvince": rows_by_count(alerts, "district__province__name"),
            "casesByDistrict": rows_by_count(alerts, "district__name"),
            "caseStatus": rows_by_count(alerts, "status"),
            "riskDistribution": rows_by_count(alerts, "priority"),
            "concernDistribution": concern_distribution(alerts),
            "monthlyTrend": monthly_alert_trend(alerts),
            "assessmentStatus": rows_by_count(alerts, "internal_status"),
            "funnel": [
                {"name": "Submitted", "value": alerts.count()},
                {"name": "Under Review", "value": alerts.filter(Q(status__icontains="Review") | Q(internal_status__icontains="Review")).count()},
                {"name": "More Information", "value": alerts.filter(Q(status__icontains="More Information") | Q(internal_status__icontains="More Information")).count()},
                {"name": "Closed", "value": closed_alerts.count()},
            ],
        },
        "tables": {
            "officerWorkload": [],
            "districtPerformance": [
                {
                    "district": row["district__name"] or "Not captured",
                    "cases": row["cases"],
                    "allocated": 0,
                    "completedAssessments": row["completed"],
                }
                for row in alerts.values("district__name").annotate(
                    cases=Count("id"),
                    completed=Count("id", filter=Q(status__icontains="Closed")),
                ).order_by("-cases")
            ],
        },
    }
