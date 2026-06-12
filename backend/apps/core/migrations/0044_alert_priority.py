from django.db import migrations, models


def backfill_alert_priority(apps, schema_editor):
    Alert = apps.get_model("core", "Alert")
    PublicSubmission = apps.get_model("core", "PublicSubmission")

    Alert.objects.filter(emergency=True).update(priority="Critical")
    Alert.objects.filter(emergency=False, priority="").update(priority="Medium")

    submissions = PublicSubmission.objects.exclude(priority="").select_related("alert").order_by("created_at", "id")
    for submission in submissions:
        alert = submission.alert
        metadata = submission.metadata if isinstance(submission.metadata, dict) else {}
        alert_reference = metadata.get("publicAlertReference")
        if not alert and alert_reference:
            alert = Alert.objects.filter(reference=alert_reference).first()
        if alert and submission.priority and alert.priority != submission.priority:
            alert.priority = submission.priority
            alert.save(update_fields=["priority"])


def clear_alert_priority(apps, schema_editor):
    Alert = apps.get_model("core", "Alert")
    Alert.objects.update(priority="Medium")


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0043_alert_programme"),
    ]

    operations = [
        migrations.AddField(
            model_name="alert",
            name="priority",
            field=models.CharField(default="Medium", max_length=40),
        ),
        migrations.RunPython(backfill_alert_priority, clear_alert_priority),
    ]
