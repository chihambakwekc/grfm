from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0051_publicsubmission_created_by"),
    ]

    operations = [
        migrations.AddField(
            model_name="district",
            name="office_address",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="district",
            name="toll_free_number",
            field=models.CharField(blank=True, max_length=40),
        ),
        migrations.AddField(
            model_name="district",
            name="whatsapp_number",
            field=models.CharField(blank=True, max_length=40),
        ),
    ]
