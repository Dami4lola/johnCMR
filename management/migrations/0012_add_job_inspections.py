from django.db import migrations, models
import django.db.models.deletion


def inspection_photo_path(instance, filename):
    job_id = instance.inspection.job.id
    inspection_type = instance.inspection.inspection_type
    return f'inspections/{job_id}/{inspection_type}/{filename}'


class Migration(migrations.Migration):

    dependencies = [
        ('management', '0011_add_purchase_list'),
    ]

    operations = [
        migrations.CreateModel(
            name='JobInspection',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('inspection_type', models.CharField(choices=[('pre', 'Pre-Inspection'), ('post', 'Post-Inspection')], max_length=4)),
                ('inspection_date', models.DateField()),
                ('inspection_time', models.TimeField(blank=True, null=True)),
                ('status', models.CharField(choices=[('draft', 'Draft'), ('completed', 'Completed')], default='draft', max_length=10)),
                ('site_conditions', models.TextField(blank=True, help_text='Overall site conditions observed')),
                ('safety_hazards', models.TextField(blank=True, help_text='Any safety hazards identified')),
                ('notes', models.TextField(blank=True, help_text='Additional observations or comments')),
                ('client_present', models.BooleanField(default=False, help_text='Was the client present during inspection?')),
                ('access_issues', models.TextField(blank=True, help_text='Any access or entry issues')),
                ('existing_damage', models.TextField(blank=True, help_text='Pre-existing damage to document')),
                ('work_completed', models.TextField(blank=True, help_text='Description of work completed')),
                ('quality_check_passed', models.BooleanField(default=True)),
                ('client_satisfied', models.BooleanField(blank=True, help_text='Client satisfaction if present', null=True)),
                ('followup_required', models.BooleanField(default=False)),
                ('followup_notes', models.TextField(blank=True, help_text='Details of any follow-up work needed')),
                ('client_signature', models.TextField(blank=True, help_text='Client signature data')),
                ('client_name_signed', models.CharField(blank=True, help_text='Printed name of client who signed', max_length=100)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('inspector', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='inspections', to='management.worker')),
                ('job', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='inspections', to='management.job')),
            ],
            options={
                'ordering': ['-inspection_date', '-created_at'],
                'unique_together': {('job', 'inspection_type')},
            },
        ),
        migrations.CreateModel(
            name='InspectionPhoto',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image', models.ImageField(upload_to='inspections/')),
                ('caption', models.CharField(blank=True, max_length=200)),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('inspection', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='photos', to='management.jobinspection')),
            ],
            options={
                'ordering': ['uploaded_at'],
            },
        ),
    ]
