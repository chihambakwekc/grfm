from django.db import migrations


PROVINCES = [
    "Bulawayo Province",
    "Harare Province",
    "Manicaland Province",
    "Mashonaland Central Province",
    "Mashonaland East Province",
    "Mashonaland West Province",
    "Masvingo Province",
    "Matabeleland North Province",
    "Matabeleland South Province",
    "Midlands Province",
]


DISTRICT_PROVINCES = {
    "Harare": "Harare Province",
    "Masvingo": "Masvingo Province",
}


def expand_geography(apps, schema_editor):
    Province = apps.get_model("core", "Province")
    District = apps.get_model("core", "District")
    Ward = apps.get_model("core", "Ward")

    province_by_name = {}
    for name in PROVINCES:
        province, _ = Province.objects.get_or_create(name=name)
        province_by_name[name] = province

    for district_name, province_name in DISTRICT_PROVINCES.items():
        District.objects.filter(name=district_name).update(province=province_by_name[province_name])

    for district in District.objects.all():
        for number in range(1, 21):
            Ward.objects.get_or_create(district=district, name=f"Ward {number}")


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0003_userprofile_must_change_password"),
    ]

    operations = [
        migrations.RunPython(expand_geography, migrations.RunPython.noop),
    ]
