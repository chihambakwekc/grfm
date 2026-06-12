from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0030_relationshiptype"),
    ]

    operations = [
        migrations.AddField(model_name="alert", name="alleged_perpetrator_known", field=models.CharField(blank=True, max_length=20)),
        migrations.AddField(model_name="alert", name="alleged_perpetrator_sex", field=models.CharField(blank=True, max_length=20)),
        migrations.AddField(model_name="alert", name="alleged_perpetrator_address", field=models.CharField(blank=True, max_length=240)),
        migrations.AddField(model_name="alert", name="referred_to_police", field=models.CharField(blank=True, max_length=20)),
        migrations.AddField(model_name="alert", name="police_reference_number", field=models.CharField(blank=True, max_length=120)),
        migrations.AddField(model_name="alert", name="police_referral_date", field=models.DateField(blank=True, null=True)),
        migrations.AddField(model_name="alert", name="court_appearance_scheduled", field=models.CharField(blank=True, max_length=20)),
        migrations.AddField(model_name="alert", name="court_appearance_date", field=models.DateField(blank=True, null=True)),
        migrations.AddField(model_name="alert", name="conviction_determined", field=models.CharField(blank=True, max_length=20)),
        migrations.AddField(model_name="alert", name="conviction_date", field=models.DateField(blank=True, null=True)),
        migrations.AddField(model_name="alert", name="circumstances_of_offence", field=models.TextField(blank=True)),
    ]
