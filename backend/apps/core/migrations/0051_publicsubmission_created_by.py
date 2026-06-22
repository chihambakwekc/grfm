from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("core", "0050_social_registry_and_community_user"),
    ]

    operations = [
        migrations.AddField(
            model_name="publicsubmission",
            name="created_by",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="public_submissions", to=settings.AUTH_USER_MODEL),
        ),
    ]
