from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0010_alert_nearest_landmark"),
    ]

    operations = [
        migrations.AlterField(
            model_name="intake",
            name="alert",
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="intake", to="core.alert"),
        ),
        migrations.AddField(
            model_name="intake",
            name="intake_source",
            field=models.CharField(blank=True, default="ALERT", max_length=80),
        ),
        migrations.AddField(
            model_name="intake",
            name="opening_summary",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="intake",
            name="original_alert_snapshot",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
