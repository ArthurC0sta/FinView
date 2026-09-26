from datetime import date
from decimal import Decimal

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class BusinessCoreMigrationTests(TransactionTestCase):
    migrate_from = [('gastos', '0005_financialgoal')]
    migrate_to = [('gastos', '0006_business_core_schema')]

    @property
    def executor(self):
        return MigrationExecutor(connection)

    def setUp(self):
        super().setUp()
        executor = self.executor
        executor.migrate(self.migrate_from)
        old_apps = executor.loader.project_state(self.migrate_from).apps
        User = old_apps.get_model('auth', 'User')
        Expense = old_apps.get_model('gastos', 'Expense')
        MonthlyIncome = old_apps.get_model('gastos', 'MonthlyIncome')
        FinancialGoal = old_apps.get_model('gastos', 'FinancialGoal')

        user = User.objects.create(username='legado@example.com', email='legado@example.com')
        MonthlyIncome.objects.create(
            user_id=user.id,
            amount=Decimal('2500.00'),
            income_type='fixed',
            reference_month=date(2026, 9, 1),
        )
        Expense.objects.create(
            user_id=user.id,
            name='Software',
            amount=Decimal('180.00'),
            date=date(2026, 9, 10),
            category='Ferramentas',
            recurrence='fixed',
            priority='essential',
        )
        FinancialGoal.objects.create(
            user_id=user.id,
            name='Reserva',
            target_amount=Decimal('5000.00'),
            saved_amount=Decimal('500.00'),
        )

        executor = self.executor
        executor.migrate(self.migrate_to)
        self.apps = executor.loader.project_state(self.migrate_to).apps

    def tearDown(self):
        self.executor.migrate(self.migrate_to)
        super().tearDown()

    def test_migra_empresa_movimentacoes_categoria_e_meta_sem_apagar_legado(self):
        Business = self.apps.get_model('gastos', 'Business')
        ManagerialCategory = self.apps.get_model('gastos', 'ManagerialCategory')
        FinancialTransaction = self.apps.get_model('gastos', 'FinancialTransaction')
        MonthlyIncome = self.apps.get_model('gastos', 'MonthlyIncome')
        Expense = self.apps.get_model('gastos', 'Expense')
        FinancialGoal = self.apps.get_model('gastos', 'FinancialGoal')

        business = Business.objects.get()
        inflow = FinancialTransaction.objects.get(direction='inflow')
        outflow = FinancialTransaction.objects.get(direction='outflow')

        self.assertTrue(business.is_default)
        self.assertEqual(inflow.amount, Decimal('2500.00'))
        self.assertEqual(inflow.category.group, 'revenue')
        self.assertEqual(outflow.amount, Decimal('180.00'))
        self.assertEqual(outflow.category.name, 'Ferramentas')
        self.assertEqual(outflow.category.group, 'unclassified')
        self.assertEqual(ManagerialCategory.objects.filter(business=business).count(), 2)
        self.assertEqual(FinancialGoal.objects.get().business_id, business.id)
        self.assertEqual(MonthlyIncome.objects.count(), 1)
        self.assertEqual(Expense.objects.count(), 1)

    def test_reversao_preserva_tabelas_legadas(self):
        executor = self.executor
        executor.migrate(self.migrate_from)
        old_apps = executor.loader.project_state(self.migrate_from).apps

        self.assertEqual(old_apps.get_model('gastos', 'MonthlyIncome').objects.count(), 1)
        self.assertEqual(old_apps.get_model('gastos', 'Expense').objects.count(), 1)
        self.assertEqual(old_apps.get_model('gastos', 'FinancialGoal').objects.count(), 1)
