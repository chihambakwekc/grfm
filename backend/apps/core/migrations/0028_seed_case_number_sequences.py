import re

from django.db import migrations


def seed_case_number_sequences(apps, schema_editor):
    District = apps.get_model("core", "District")
    Intake = apps.get_model("core", "Intake")
    CaseNumberSequence = apps.get_model("core", "CaseNumberSequence")
    max_seen = {}
    districts_by_code = {district.code.upper(): district for district in District.objects.all()}

    for intake in Intake.objects.select_related("alert__district"):
        code = ""
        year = None
        number = None

        direct = re.match(r"^([A-Z]{3})/(\d{4})/(\d+)$", intake.temporary_case_reference or "")
        if direct:
            code, year, number = direct.group(1), int(direct.group(2)), int(direct.group(3))
        elif intake.alert_id and intake.alert and intake.alert.reference:
            alert_match = re.match(r"^ALT-(\d{4})-([A-Z]{3})-(\d+)$", intake.alert.reference)
            if alert_match:
                year, code, number = int(alert_match.group(1)), alert_match.group(2), int(alert_match.group(3))
        elif intake.alert_id and intake.alert and intake.alert.district_id:
            district = intake.alert.district
            code = (district.code or "").upper()

        if not (code and year and number):
            continue
        district = districts_by_code.get(code)
        if not district:
            continue
        key = (district.id, year)
        max_seen[key] = max(max_seen.get(key, 0), number)

    for (district_id, year), highest in max_seen.items():
        sequence, _ = CaseNumberSequence.objects.get_or_create(
            district_id=district_id,
            year=year,
            defaults={"next_number": highest + 1},
        )
        if sequence.next_number <= highest:
            sequence.next_number = highest + 1
            sequence.save(update_fields=["next_number"])


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0027_district_code_case_number_sequence"),
    ]

    operations = [
        migrations.RunPython(seed_case_number_sequences, migrations.RunPython.noop),
    ]
