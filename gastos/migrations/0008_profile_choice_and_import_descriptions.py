from django.db import migrations, models


def initialize_new_fields(apps, schema_editor):
    Assessment = apps.get_model('gastos', 'BusinessProfileAssessment')
    ImportRow = apps.get_model('gastos', 'ImportRow')
    for assessment in Assessment.objects.all().iterator():
        assessment.selected_level = assessment.recommended_level
        preferences = dict(assessment.preferences or {})
        preferences.pop('focus', None)
        assessment.preferences = preferences
        assessment.save(update_fields=['selected_level', 'preferences'])
    for row in ImportRow.objects.all().iterator():
        row.original_description = row.description
        row.save(update_fields=['original_description'])


def reverse_initialize(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [('gastos', '0007_platform_expansion')]
    operations = [
        migrations.AddField(
            model_name='businessprofileassessment', name='selected_level',
            field=models.CharField(blank=True, choices=[('essential', 'Essencial'), ('managerial', 'Gerencial'), ('complete', 'Completa')], max_length=20),
        ),
        migrations.AddField(
            model_name='businessprofileassessment', name='level_override_reason',
            field=models.CharField(blank=True, max_length=240),
        ),
        migrations.AddField(model_name='importrow', name='original_description', field=models.CharField(blank=True, max_length=240)),
        migrations.AddField(model_name='importrow', name='suggested_description', field=models.CharField(blank=True, max_length=240)),
        migrations.CreateModel(
            name='ExternalMigrationRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('source', models.CharField(max_length=30)), ('entity', models.CharField(max_length=40)),
                ('external_id', models.CharField(max_length=120)), ('local_model', models.CharField(max_length=80)),
                ('local_id', models.CharField(max_length=120)), ('migrated_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.AddConstraint(
            model_name='externalmigrationrecord',
            constraint=models.UniqueConstraint(fields=('source', 'entity', 'external_id'), name='unique_external_migration_record'),
        ),
        migrations.RunPython(initialize_new_fields, reverse_initialize),
    ]
