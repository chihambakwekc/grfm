from django.db import migrations


HARARE_WARDS = ["Ward 1", "Ward 2", "Ward 3", "Ward 4", "Ward 5"]


def seed_harare_wards(apps, schema_editor):
    Province = apps.get_model("core", "Province")
    District = apps.get_model("core", "District")
    Ward = apps.get_model("core", "Ward")

    province, _ = Province.objects.get_or_create(name="Harare Province", defaults={"status": "Active"})
    district, _ = District.objects.get_or_create(
        name="Harare",
        defaults={"province": province, "code": "HAR", "status": "Active"},
    )
    if district.province_id != province.id:
        district.province = province
        district.save(update_fields=["province"])

    for name in HARARE_WARDS:
        Ward.objects.update_or_create(
            district=district,
            name=name,
            defaults={"province": province, "status": "Active"},
        )
    Ward.objects.filter(district=district).exclude(name__in=HARARE_WARDS).update(status="Inactive")


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0040_update_internal_roles"),
    ]

    operations = [
        migrations.RunPython(seed_harare_wards, noop),
    ]
