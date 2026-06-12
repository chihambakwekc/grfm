import re

from django.db import migrations


def next_reference(existing, prefix, district_code):
    district_code = (district_code or "UNK").strip().upper()
    stem = f"{prefix}-{district_code}-"
    highest = 0
    for reference in existing:
        match = re.match(rf"^{re.escape(stem)}(\d+)$", reference or "")
        if match:
            highest = max(highest, int(match.group(1)))
    reference = f"{stem}{highest + 1:03d}"
    existing.add(reference)
    return reference


def alert_prefix(alert):
    if alert.intake_source == "PUBLIC_ABUSE_REPORT" or alert.emergency:
        return "ABU"
    return "CMP"


def forwards(apps, schema_editor):
    Alert = apps.get_model("core", "Alert")
    PublicSubmission = apps.get_model("core", "PublicSubmission")

    existing_alert_refs = set()
    for alert in Alert.objects.select_related("district").order_by("created_at", "id"):
        district_code = alert.district.code if alert.district_id else "UNK"
        if re.match(r"^(CMP|ABU)-[A-Z]{3}-\d{3}$", alert.reference or ""):
            existing_alert_refs.add(alert.reference)
            continue
        alert.reference = next_reference(existing_alert_refs, alert_prefix(alert), district_code)
        alert.save(update_fields=["reference"])

    prefix_by_type = {
        "COMPLAINT": "CMP",
        "ABUSE": "ABU",
        "FEEDBACK": "GFB",
        "VOICE": "VOR",
    }
    existing_submission_refs = set()
    for submission in PublicSubmission.objects.select_related("district").order_by("created_at", "id"):
        district_code = submission.district.code if submission.district_id else "UNK"
        if re.match(r"^(CMP|ABU|GFB|VOR)-[A-Z]{3}-\d{3}$", submission.reference or ""):
            existing_submission_refs.add(submission.reference)
            continue
        submission.reference = next_reference(existing_submission_refs, prefix_by_type.get(submission.submission_type, "PUB"), district_code)
        submission.save(update_fields=["reference"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0041_seed_harare_wards"),
    ]

    operations = [
        migrations.RunPython(forwards, noop),
    ]
