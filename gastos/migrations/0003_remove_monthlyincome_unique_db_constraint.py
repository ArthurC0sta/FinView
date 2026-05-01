from django.db import migrations


def remove_monthly_income_unique_constraint(apps, schema_editor):
    table = 'gastos_monthlyincome'
    columns = ['user_id', 'reference_month']
    connection = schema_editor.connection

    with connection.cursor() as cursor:
        constraints = connection.introspection.get_constraints(cursor, table)
        matching_names = [
            name
            for name, details in constraints.items()
            if details.get('unique') and details.get('columns') == columns
        ]

    if not matching_names:
        return

    if connection.vendor == 'sqlite':
        schema_editor.execute('PRAGMA foreign_keys=OFF')
        schema_editor.execute(
            '''
            CREATE TABLE gastos_monthlyincome_new (
                id integer NOT NULL PRIMARY KEY AUTOINCREMENT,
                amount decimal NOT NULL,
                income_type varchar(20) NOT NULL,
                reference_month date NOT NULL,
                created_at datetime NOT NULL,
                updated_at datetime NOT NULL,
                user_id integer NOT NULL REFERENCES auth_user(id) DEFERRABLE INITIALLY DEFERRED
            )
            '''
        )
        schema_editor.execute(
            '''
            INSERT INTO gastos_monthlyincome_new (
                id, amount, income_type, reference_month, created_at, updated_at, user_id
            )
            SELECT id, amount, income_type, reference_month, created_at, updated_at, user_id
            FROM gastos_monthlyincome
            '''
        )
        schema_editor.execute('DROP TABLE gastos_monthlyincome')
        schema_editor.execute('ALTER TABLE gastos_monthlyincome_new RENAME TO gastos_monthlyincome')
        schema_editor.execute('CREATE INDEX gastos_monthlyincome_user_id_be72677b ON gastos_monthlyincome(user_id)')
        schema_editor.execute('PRAGMA foreign_keys=ON')
        return

    if connection.vendor == 'postgresql':
        for name in matching_names:
            schema_editor.execute(f'ALTER TABLE {table} DROP CONSTRAINT IF EXISTS "{name}"')


class Migration(migrations.Migration):

    dependencies = [
        ('gastos', '0002_monthlyincome_multiple_entries'),
    ]

    operations = [
        migrations.RunPython(remove_monthly_income_unique_constraint, migrations.RunPython.noop),
    ]
