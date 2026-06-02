from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("trustlists", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="lotlpointer",
            name="cert_pem",
            field=models.TextField(
                blank=True,
                help_text="PEM-encoded signing certificate for this pointer's ServiceDigitalIdentity",
            ),
        ),
    ]
