from django.db import migrations


def normalize_status(value):
    status = str(value or "").strip().lower()
    if status in {"new", "assigned", "in progress", "escalated", "closed"}:
        return value
    if any(term in status for term in ["closed", "closure approved", "referred", "rejected", "duplicate", "resolved", "completed", "no further action"]):
        return "Closed"
    if any(term in status for term in ["escalated", "emergency", "immediate", "critical"]):
        return "Escalated"
    if any(term in status for term in ["assigned", "allocated"]):
        return "Assigned"
    if any(term in status for term in ["progress", "review", "ready", "more information", "closure requested", "returned", "intake"]):
        return "In Progress"
    return "New"


def forwards(apps, schema_editor):
    Alert = apps.get_model("core", "Alert")
    for alert in Alert.objects.all().only("id", "internal_status"):
        next_status = normalize_status(alert.internal_status)
        if alert.internal_status != next_status:
            alert.internal_status = next_status
            alert.save(update_fields=["internal_status"])


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0045_alter_alert_internal_status"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
