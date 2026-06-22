from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0052_district_contact_details"),
    ]

    operations = [
        migrations.AddField(
            model_name="province",
            name="office_address",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="province",
            name="toll_free_number",
            field=models.CharField(blank=True, max_length=40),
        ),
        migrations.AddField(
            model_name="province",
            name="whatsapp_number",
            field=models.CharField(blank=True, max_length=40),
        ),
    ]
