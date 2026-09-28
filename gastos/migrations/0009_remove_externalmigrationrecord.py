from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [('gastos', '0008_profile_choice_and_import_descriptions')]

    operations = [
        migrations.DeleteModel(name='ExternalMigrationRecord'),
    ]
