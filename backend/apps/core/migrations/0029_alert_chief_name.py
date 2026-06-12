from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0028_seed_case_number_sequences"),
    ]

    operations = [
        migrations.AddField(
            model_name="alert",
            name="chief_name",
            field=models.CharField(blank=True, max_length=160),
        ),
    ]
