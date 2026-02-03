from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('management', '0010_add_job_distance'),
    ]

    operations = [
        migrations.CreateModel(
            name='PurchaseListItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text='Item name/description', max_length=200)),
                ('quantity', models.CharField(blank=True, help_text="e.g., '2 boxes', '5 bags'", max_length=50)),
                ('priority', models.CharField(choices=[('1_high', 'High - Urgent'), ('2_medium', 'Medium'), ('3_low', 'Low')], default='2_medium', max_length=10)),
                ('status', models.CharField(choices=[('needed', 'Needed'), ('purchased', 'Purchased')], default='needed', max_length=10)),
                ('notes', models.TextField(blank=True, help_text='Additional details (brand, size, where to buy, etc.)')),
                ('added_at', models.DateTimeField(auto_now_add=True)),
                ('purchased_at', models.DateTimeField(blank=True, null=True)),
                ('added_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='purchase_items_added', to=settings.AUTH_USER_MODEL)),
                ('purchased_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='purchase_items_bought', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['priority', '-added_at'],
            },
        ),
    ]
