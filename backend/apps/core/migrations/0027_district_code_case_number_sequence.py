from django.core.validators import RegexValidator
from django.db import migrations, models
import django.db.models.deletion


def normalize_district_codes(apps, schema_editor):
    District = apps.get_model("core", "District")
    used = set()
    for district in District.objects.order_by("id"):
        base = "".join(ch for ch in (district.code or "").upper() if ch.isalpha())[:3]
        if len(base) < 3:
            base = "".join(ch for ch in (district.name or "").upper() if ch.isalpha())[:3]
        if len(base) < 3:
            base = "DST"
        code = base
        suffix = 1
        while code in used or District.objects.exclude(pk=district.pk).filter(code__iexact=code).exists():
            seed = "".join(ch for ch in (district.name or "DST").upper() if ch.isalpha())[:2] or "D"
            code = f"{seed}{chr(65 + (suffix % 26))}"[:3]
            suffix += 1
        district.code = code
        district.save(update_fields=["code"])
        used.add(code)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0026_intake_closure_draft_and_history"),
    ]

    operations = [
        migrations.RunPython(normalize_district_codes, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="district",
            name="code",
            field=models.CharField(
                max_length=3,
                unique=True,
                validators=[
                    RegexValidator(
                        regex="^[A-Z]{3}$",
                        message="District code must be exactly 3 uppercase letters.",
                    )
                ],
            ),
        ),
        migrations.CreateModel(
            name="CaseNumberSequence",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("year", models.PositiveIntegerField()),
                ("next_number", models.PositiveIntegerField(default=1)),
                ("district", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="case_number_sequences", to="core.district")),
            ],
            options={
                "ordering": ("district__code", "year"),
                "unique_together": {("district", "year")},
            },
        ),
    ]
