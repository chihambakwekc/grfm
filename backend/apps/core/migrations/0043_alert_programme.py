from django.db import migrations, models


def backfill_alert_programme(apps, schema_editor):
    Alert = apps.get_model("core", "Alert")
    PublicSubmission = apps.get_model("core", "PublicSubmission")

    submissions = PublicSubmission.objects.exclude(programme="").select_related("alert").order_by("created_at", "id")
    for submission in submissions:
        alert = submission.alert
        metadata = submission.metadata if isinstance(submission.metadata, dict) else {}
        alert_reference = metadata.get("publicAlertReference")
        if not alert and alert_reference:
            alert = Alert.objects.filter(reference=alert_reference).first()
        if alert and not alert.programme:
            alert.programme = submission.programme
            alert.save(update_fields=["programme"])


def clear_alert_programme(apps, schema_editor):
    Alert = apps.get_model("core", "Alert")
    Alert.objects.update(programme="")


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0042_grfm_public_reference_conventions"),
    ]

    operations = [
        migrations.AddField(
            model_name="alert",
            name="programme",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.RunPython(backfill_alert_programme, clear_alert_programme),
    ]
