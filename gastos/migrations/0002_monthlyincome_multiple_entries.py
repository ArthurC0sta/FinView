from django.db import migrations, models


def convert_mixed_income_types(apps, schema_editor):
    MonthlyIncome = apps.get_model('gastos', 'MonthlyIncome')
    MonthlyIncome.objects.filter(income_type='mixed').update(income_type='variable')


class Migration(migrations.Migration):

    dependencies = [
        ('gastos', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(convert_mixed_income_types, migrations.RunPython.noop),
        migrations.AlterUniqueTogether(
            name='monthlyincome',
            unique_together=set(),
        ),
        migrations.AlterField(
            model_name='monthlyincome',
            name='income_type',
            field=models.CharField(choices=[('fixed', 'Salário fixo'), ('variable', 'Freelance / Variável')], default='fixed', max_length=20),
        ),
    ]
