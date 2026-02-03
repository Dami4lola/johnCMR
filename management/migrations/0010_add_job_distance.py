from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('management', '0009_add_receipt_model'),
    ]

    operations = [
        migrations.AddField(
            model_name='job',
            name='calculated_distance_km',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='Auto-calculated round trip distance from office (km)',
                max_digits=6,
                null=True
            ),
        ),
    ]
