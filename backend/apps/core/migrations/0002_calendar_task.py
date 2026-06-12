from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("core", "0001_phase1"),
    ]

    operations = [
        migrations.CreateModel(
            name="CalendarTask",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=160)),
                ("detail", models.CharField(blank=True, max_length=240)),
                ("date", models.DateField()),
                ("urgent", models.BooleanField(default=False)),
                ("source", models.CharField(blank=True, max_length=80)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="calendar_tasks", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ("date", "title"),
                "unique_together": {("source", "title", "date")},
            },
        ),
    ]
