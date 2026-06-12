from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0006_prune_roles_and_add_profile_province"),
    ]

    operations = [
        migrations.AddField(
            model_name="alert",
            name="intake_source",
            field=models.CharField(blank=True, default="ALERT", max_length=80),
        ),
        migrations.AddField(
            model_name="alert",
            name="reporting_channel",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="alert",
            name="information_source_type",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="alert",
            name="information_source_name",
            field=models.CharField(blank=True, max_length=160),
        ),
        migrations.AddField(
            model_name="alert",
            name="information_source_contact",
            field=models.CharField(blank=True, max_length=80),
        ),
        migrations.AddField(
            model_name="alert",
            name="information_source_relationship_to_child",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="alert",
            name="protect_source_identity",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="alert",
            name="alternative_contact",
            field=models.CharField(blank=True, max_length=80),
        ),
    ]
