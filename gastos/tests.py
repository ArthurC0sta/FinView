import re
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from urllib.parse import urlparse

from django.contrib.auth.models import User
from django.core import mail
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from unittest.mock import patch

from .ia import classificar_descricoes, carregar_prompt_consultor, gerar_resposta_financeira
from .models import (
    Business,
    BusinessProfileAssessment,
    FinancialGoal,
    FinancialTransaction,
    ManagerialCategory,
    MonthlyIncome,
)


def complete_profile(user):
    business = user.businesses.get(is_default=True)
    return BusinessProfileAssessment.objects.create(
        business=business,
        maturity_answers={'records': '1'},
        score=12,
        recommended_level=BusinessProfileAssessment.Level.MANAGERIAL,
        status=BusinessProfileAssessment.Status.COMPLETED,
        completed_at=timezone.now(),
    )
from .views import (
    active_goals_for_user,
    ai_context_for_month,
    current_month_date,
    ensure_fixed_expenses_for_month,
)


class BusinessCoreModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='empresa@example.com',
            email='empresa@example.com',
            password='senha12345',
        )
        self.business = self.user.businesses.get(is_default=True)

    def test_usuario_possui_uma_empresa_padrao(self):
        self.assertEqual(Business.objects.filter(owner=self.user, is_default=True).count(), 1)

    def test_categoria_tem_nome_visivel_e_grupo_gerencial(self):
        category = ManagerialCategory.objects.create(
            business=self.business,
            name='Software',
            group=ManagerialCategory.Group.ADMINISTRATIVE,
        )

        self.assertEqual(category.name, 'Software')
        self.assertEqual(category.group, ManagerialCategory.Group.ADMINISTRATIVE)

    def test_movimentacao_exige_valor_positivo(self):
        category = ManagerialCategory.objects.create(
            business=self.business,
            name='Não classificadas',
            group=ManagerialCategory.Group.UNCLASSIFIED,
        )
        transaction = FinancialTransaction(
            business=self.business,
            created_by=self.user,
            direction=FinancialTransaction.Direction.OUTFLOW,
            name='Valor inválido',
            amount=Decimal('0.00'),
            date=timezone.localdate(),
            category=category,
        )

        with self.assertRaises(ValidationError):
            transaction.full_clean()


class BusinessCoreFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='gestora@example.com',
            email='gestora@example.com',
            password='senha12345',
        )
        self.other_user = User.objects.create_user(
            username='outra@example.com',
            email='outra@example.com',
            password='senha12345',
        )
        self.business = self.user.businesses.get(is_default=True)
        self.category = ManagerialCategory.objects.create(
            business=self.business,
            name='Software',
            group=ManagerialCategory.Group.ADMINISTRATIVE,
        )
        complete_profile(self.user)
        self.client.force_login(self.user)

    def transaction(self, *, direction, amount, name='Lançamento', date=None, recurrence='variable'):
        return FinancialTransaction.objects.create(
            business=self.business,
            created_by=self.user,
            direction=direction,
            name=name,
            amount=amount,
            date=date or current_month_date(),
            category=self.category,
            recurrence=recurrence,
        )

    def test_cadastro_de_despesa_grava_movimentacao_da_empresa(self):
        response = self.client.post(
            reverse('gastos:new_expense'),
            {
                'name': 'Hospedagem',
                'amount': '149,90',
                'date': current_month_date().isoformat(),
                'category': 'Infraestrutura',
                'recurrence': 'fixed',
                'priority': 'important',
                'notes': 'Servidor da aplicação',
            },
        )

        transaction = FinancialTransaction.objects.get(name='Hospedagem')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(transaction.business, self.business)
        self.assertEqual(transaction.created_by, self.user)
        self.assertEqual(transaction.direction, FinancialTransaction.Direction.OUTFLOW)
        self.assertEqual(transaction.amount, Decimal('149.90'))
        self.assertEqual(transaction.category.name, 'Infraestrutura')
        self.assertEqual(transaction.category.group, ManagerialCategory.Group.UNCLASSIFIED)

    def test_valores_nao_positivos_sao_rejeitados_nos_fluxos(self):
        month = current_month_date()
        income_response = self.client.post(
            reverse('gastos:monthly'),
            {'reference_month': month.strftime('%Y-%m'), 'income_amount': '0', 'income_type': 'fixed'},
        )
        expense_response = self.client.post(
            reverse('gastos:new_expense'),
            {
                'name': 'Inválida',
                'amount': '-10',
                'date': month.isoformat(),
                'category': 'Outros',
            },
        )

        self.assertEqual(income_response.status_code, 302)
        self.assertEqual(expense_response.status_code, 302)
        self.assertFalse(FinancialTransaction.objects.filter(business=self.business).exists())

    def test_edicao_e_exclusao_de_outra_empresa_retornam_404(self):
        other_business = self.other_user.businesses.get(is_default=True)
        other_category = ManagerialCategory.objects.create(
            business=other_business,
            name='Outros',
        )
        other_transaction = FinancialTransaction.objects.create(
            business=other_business,
            created_by=self.other_user,
            direction=FinancialTransaction.Direction.OUTFLOW,
            name='Dado protegido',
            amount='80.00',
            date=current_month_date(),
            category=other_category,
        )

        edit_response = self.client.post(
            reverse('gastos:edit_expense', args=[other_transaction.id]),
            {
                'name': 'Tentativa',
                'amount': '1.00',
                'date': current_month_date().isoformat(),
                'category': 'Outros',
            },
        )
        delete_response = self.client.post(
            reverse('gastos:delete_expense', args=[other_transaction.id]),
        )

        other_transaction.refresh_from_db()
        self.assertEqual(edit_response.status_code, 404)
        self.assertEqual(delete_response.status_code, 404)
        self.assertEqual(other_transaction.name, 'Dado protegido')

    def test_dashboard_calcula_totais_apenas_com_movimentacoes(self):
        month = current_month_date()
        self.transaction(direction=FinancialTransaction.Direction.INFLOW, amount='3000.00', name='Receita', date=month)
        self.transaction(direction=FinancialTransaction.Direction.OUTFLOW, amount='750.00', name='Despesa', date=month)
        MonthlyIncome.objects.create(user=self.user, amount='9999.00', income_type='fixed', reference_month=month)

        response = self.client.get(reverse('gastos:dashboard'), {'month': month.strftime('%Y-%m')})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['income_amount_display'], 'R$ 3.000,00')
        self.assertEqual(response.context['total_expenses_display'], 'R$ 750,00')
        self.assertEqual(response.context['balance_display'], 'R$ 2.250,00')

    def test_recorrencia_fixa_nao_duplica_no_mes_destino(self):
        source_month = current_month_date()
        if source_month.month == 12:
            target_month = source_month.replace(year=source_month.year + 1, month=1)
        else:
            target_month = source_month.replace(month=source_month.month + 1)
        self.transaction(
            direction=FinancialTransaction.Direction.OUTFLOW,
            amount='200.00',
            name='Contabilidade',
            date=source_month,
            recurrence='fixed',
        )

        ensure_fixed_expenses_for_month(self.user, target_month)
        ensure_fixed_expenses_for_month(self.user, target_month)

        self.assertEqual(
            FinancialTransaction.objects.filter(
                business=self.business,
                name='Contabilidade',
                date__year=target_month.year,
                date__month=target_month.month,
            ).count(),
            1,
        )

    def test_meta_e_contexto_da_ia_usam_empresa_corrente(self):
        month = current_month_date()
        self.transaction(direction=FinancialTransaction.Direction.INFLOW, amount='4000.00', name='Receita', date=month)
        self.transaction(direction=FinancialTransaction.Direction.OUTFLOW, amount='1000.00', name='Software', date=month)
        response = self.client.post(
            reverse('gastos:goals'),
            {
                'name': 'Reserva empresarial',
                'target_amount': '10000.00',
                'saved_amount': '1000.00',
                'target_date': '',
                'goal_type': 'emergency',
                'priority': 'high',
                'status': 'active',
                'notes': '',
            },
        )

        goal = FinancialGoal.objects.get(name='Reserva empresarial')
        context = ai_context_for_month(self.user, month)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(goal.business, self.business)
        self.assertIn('Renda cadastrada: R$ 4.000,00', context)
        self.assertIn('Total de despesas: R$ 1.000,00', context)
        self.assertIn('Reserva empresarial', context)


class FinancialGoalModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='ana@example.com',
            email='ana@example.com',
            password='senha12345',
        )

    def test_calcula_progresso_e_valores_sem_prazo(self):
        goal = FinancialGoal(
            user=self.user,
            name='Reserva',
            target_amount=Decimal('1000.00'),
            saved_amount=Decimal('250.00'),
        )

        self.assertEqual(goal.remaining_amount, Decimal('750.00'))
        self.assertEqual(goal.progress_percent, 25)
        self.assertIsNone(goal.months_remaining)
        self.assertIsNone(goal.required_monthly_amount)
        self.assertFalse(goal.is_completed)

    def test_meta_concluida_no_mes_atual_tem_calculos_limitados(self):
        goal = FinancialGoal(
            user=self.user,
            name='Notebook',
            target_amount=Decimal('3000.00'),
            saved_amount=Decimal('3000.00'),
            target_date=timezone.localdate(),
        )

        self.assertEqual(goal.remaining_amount, Decimal('0.00'))
        self.assertEqual(goal.progress_percent, 100)
        self.assertEqual(goal.months_remaining, 1)
        self.assertEqual(goal.required_monthly_amount, Decimal('0.00'))
        self.assertTrue(goal.is_completed)

    def test_rejeita_valores_impossiveis_e_prazo_passado(self):
        invalid_goals = [
            FinancialGoal(user=self.user, name='Alvo zero', target_amount=0, saved_amount=0),
            FinancialGoal(user=self.user, name='Negativa', target_amount=100, saved_amount=-1),
            FinancialGoal(user=self.user, name='Acima do alvo', target_amount=100, saved_amount=101),
            FinancialGoal(
                user=self.user,
                name='Prazo vencido',
                target_amount=100,
                saved_amount=0,
                target_date=timezone.localdate() - timedelta(days=1),
            ),
        ]

        for goal in invalid_goals:
            with self.subTest(goal=goal.name):
                with self.assertRaises(ValidationError):
                    goal.full_clean()


class FinancialGoalViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='ana@example.com',
            email='ana@example.com',
            password='senha12345',
        )
        self.other_user = User.objects.create_user(
            username='bia@example.com',
            email='bia@example.com',
            password='senha12345',
        )
        complete_profile(self.user)
        self.client.force_login(self.user)

    def goal_data(self, **overrides):
        data = {
            'name': 'Reserva de emergência',
            'target_amount': '6000.00',
            'saved_amount': '500.00',
            'target_date': (timezone.localdate() + timedelta(days=180)).isoformat(),
            'goal_type': 'emergency',
            'priority': 'high',
            'notes': 'Cobrir seis meses de despesas.',
        }
        data.update(overrides)
        return data

    def create_goal(self, user=None, **overrides):
        data = self.goal_data(**overrides)
        return FinancialGoal.objects.create(user=user or self.user, **data)

    def test_cria_meta_valida_para_usuario_autenticado(self):
        response = self.client.post(
            reverse('gastos:goals'),
            self.goal_data(target_amount='6.000,00', saved_amount='500,00'),
        )

        self.assertRedirects(response, reverse('gastos:goals'))
        goal = FinancialGoal.objects.get()
        self.assertEqual(goal.user, self.user)
        self.assertEqual(goal.name, 'Reserva de emergência')
        self.assertEqual(goal.target_amount, Decimal('6000.00'))
        self.assertEqual(goal.saved_amount, Decimal('500.00'))
        self.assertEqual(goal.status, 'active')

    def test_pagina_renderiza_calculos_da_meta_persistida(self):
        response = self.client.post(
            reverse('gastos:goals'),
            self.goal_data(target_amount='1000.00', saved_amount='250.00', target_date=''),
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Reserva de emergência')
        self.assertContains(response, 'R$ 750,00')
        self.assertContains(response, '25%')
        self.assertContains(response, 'Sem prazo definido', count=2)

    def test_rejeita_entradas_invalidas_sem_perder_valores_do_formulario(self):
        invalid_cases = [
            ({'name': ''}, 'name', 'Este campo é obrigatório.'),
            ({'target_amount': '0'}, 'target_amount', 'O valor alvo deve ser maior que zero.'),
            ({'saved_amount': '-1'}, 'saved_amount', 'O valor guardado não pode ser negativo.'),
            ({'saved_amount': '7000'}, 'saved_amount', 'O valor guardado não pode ser maior que o valor alvo.'),
            (
                {'target_date': (timezone.localdate() - timedelta(days=1)).isoformat()},
                'target_date',
                'O prazo não pode estar no passado.',
            ),
            ({'goal_type': 'invalid'}, 'goal_type', 'Faça uma escolha válida.'),
        ]

        for overrides, field, message in invalid_cases:
            with self.subTest(field=field, overrides=overrides):
                submitted_data = self.goal_data(**overrides)
                response = self.client.post(reverse('gastos:goals'), submitted_data)

                self.assertEqual(response.status_code, 200)
                self.assertFormError(response.context['form'], field, message)
                self.assertEqual(response.context['form'][field].value(), submitted_data[field])
                self.assertEqual(FinancialGoal.objects.count(), 0)

    def test_pagina_e_criacao_exigem_login_sem_persistir(self):
        self.client.logout()

        get_response = self.client.get(reverse('gastos:goals'))
        post_response = self.client.post(reverse('gastos:goals'), self.goal_data())

        self.assertRedirects(get_response, reverse('gastos:login'))
        self.assertRedirects(post_response, reverse('gastos:login'))
        self.assertEqual(FinancialGoal.objects.count(), 0)

    def test_pagina_lista_somente_metas_do_usuario(self):
        self.create_goal(name='Meta da Ana')
        self.create_goal(name='Meta pausada da Ana', status='paused')
        self.create_goal(name='Meta concluída da Ana', status='completed')
        self.create_goal(user=self.other_user, name='Meta da Bia')

        response = self.client.get(reverse('gastos:goals'))

        self.assertContains(response, 'Meta da Ana')
        self.assertContains(response, 'Meta pausada da Ana')
        self.assertContains(response, 'Meta concluída da Ana')
        self.assertNotContains(response, 'Meta da Bia')

    def test_dono_exclui_meta_com_post(self):
        goal = self.create_goal()

        response = self.client.post(reverse('gastos:delete_goal', args=[goal.id]))

        self.assertRedirects(response, reverse('gastos:goals'))
        self.assertFalse(FinancialGoal.objects.filter(id=goal.id).exists())

    def test_usuario_nao_exclui_meta_de_outro_usuario(self):
        goal = self.create_goal(user=self.other_user)

        response = self.client.post(reverse('gastos:delete_goal', args=[goal.id]))

        self.assertEqual(response.status_code, 404)
        self.assertTrue(FinancialGoal.objects.filter(id=goal.id).exists())

    def test_usuario_nao_autenticado_nao_exclui_meta(self):
        goal = self.create_goal()
        self.client.logout()

        response = self.client.post(reverse('gastos:delete_goal', args=[goal.id]))

        self.assertRedirects(response, reverse('gastos:login'))
        self.assertTrue(FinancialGoal.objects.filter(id=goal.id).exists())

    def test_exclusao_rejeita_get(self):
        goal = self.create_goal()

        response = self.client.get(reverse('gastos:delete_goal', args=[goal.id]))

        self.assertEqual(response.status_code, 405)
        self.assertTrue(FinancialGoal.objects.filter(id=goal.id).exists())


class FinancialGoalContextTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='ana@example.com',
            email='ana@example.com',
            password='senha12345',
        )
        complete_profile(self.user)

    def create_goal(self, name, status='active'):
        return FinancialGoal.objects.create(
            user=self.user,
            name=name,
            target_amount=Decimal('1000.00'),
            saved_amount=Decimal('100.00'),
            status=status,
        )

    def test_dashboard_e_ia_consideram_somente_metas_ativas(self):
        active_goal_names = [f'Meta ativa {index}' for index in range(1, 5)]
        for name in active_goal_names:
            self.create_goal(name)
        self.create_goal('Meta pausada', status='paused')
        self.client.force_login(self.user)

        dashboard_response = self.client.get(reverse('gastos:dashboard'))
        ai_context = ai_context_for_month(self.user, current_month_date())
        dashboard_goals = dashboard_response.context['goals']
        active_names = list(active_goals_for_user(self.user).values_list('name', flat=True))

        self.assertEqual(dashboard_response.status_code, 200)
        self.assertCountEqual([goal['name'] for goal in dashboard_goals], active_goal_names)
        self.assertNotContains(dashboard_response, 'Meta pausada')
        for name in active_goal_names:
            self.assertIn(name, ai_context)
        self.assertNotIn('Meta pausada', ai_context)
        self.assertCountEqual(active_names, active_goal_names)

    def test_contextos_sem_meta_ativa_continuam_validos(self):
        self.create_goal('Meta concluída', status='completed')
        self.client.force_login(self.user)

        dashboard_response = self.client.get(reverse('gastos:dashboard'))
        ai_context = ai_context_for_month(self.user, current_month_date())

        self.assertEqual(dashboard_response.status_code, 200)
        self.assertContains(dashboard_response, 'Nenhuma meta financeira ativa')
        self.assertIn('sem metas financeiras cadastradas', ai_context)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class PasswordResetFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='ana@example.com',
            email='ana@example.com',
            password='senha12345',
        )

    def test_login_aponta_para_recuperacao_de_senha(self):
        response = self.client.get(reverse('gastos:login'))

        self.assertContains(response, reverse('gastos:password_reset'))

    def test_solicitacao_envia_link_sem_expor_se_conta_existe(self):
        response = self.client.post(
            reverse('gastos:password_reset'),
            {'email': self.user.email},
        )

        self.assertRedirects(response, reverse('gastos:password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Redefinição de senha', mail.outbox[0].subject)
        self.assertIn('/reset/', mail.outbox[0].body)

        mail.outbox.clear()
        response = self.client.post(
            reverse('gastos:password_reset'),
            {'email': 'conta-inexistente@example.com'},
        )

        self.assertRedirects(response, reverse('gastos:password_reset_done'))
        self.assertEqual(mail.outbox, [])

    def test_usuario_redefine_senha_com_token_valido(self):
        self.client.post(
            reverse('gastos:password_reset'),
            {'email': self.user.email},
        )
        reset_url = re.search(r'https?://[^\s]+', mail.outbox[0].body).group(0)
        token_response = self.client.get(urlparse(reset_url).path)

        self.assertEqual(token_response.status_code, 302)
        set_password_url = token_response.url
        response = self.client.post(
            set_password_url,
            {
                'new_password1': 'NovaSenhaSegura2026!',
                'new_password2': 'NovaSenhaSegura2026!',
            },
        )

        self.assertRedirects(response, reverse('gastos:password_reset_complete'))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('NovaSenhaSegura2026!'))

    def test_link_invalido_exibe_opcao_para_nova_solicitacao(self):
        response = self.client.get('/reset/uid-invalido/token-invalido/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Link inválido ou expirado')
        self.assertContains(response, reverse('gastos:password_reset'))


class GroqIntegrationTests(TestCase):
    def tearDown(self):
        carregar_prompt_consultor.cache_clear()

    def test_prompt_da_api_carrega_skill_local_com_limites_consultivos(self):
        prompt = carregar_prompt_consultor()

        self.assertIn('estudos de mercado', prompt)
        self.assertIn('mestrado e doutorado', prompt)
        self.assertIn('consultiva e educacional', prompt)
        self.assertIn('contador habilitado', prompt)
        self.assertIn('deve ser verificada', prompt)

    @override_settings(
        GROQ_API_KEY='test-key',
        GROQ_MODEL='legacy-model',
        GROQ_ANALYSIS_MODEL='analysis-model',
        GROQ_CLASSIFICATION_MODEL='classification-model',
        GROQ_TIMEOUT_SECONDS=20,
    )
    @patch('gastos.ia.Groq')
    def test_gerar_resposta_financeira_usa_chave_e_modelo_configurados(self, groq_mock):
        groq_mock.return_value.chat.completions.create.return_value = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=' Insight financeiro gerado. ')
                )
            ]
        )

        response = gerar_resposta_financeira('Analise meu mes.', 'Renda: R$ 1000')

        self.assertEqual(response, 'Insight financeiro gerado.')
        groq_mock.assert_called_once_with(api_key='test-key', timeout=20, max_retries=1)
        groq_mock.return_value.chat.completions.create.assert_called_once()
        call_kwargs = groq_mock.return_value.chat.completions.create.call_args.kwargs
        self.assertEqual(call_kwargs['model'], 'analysis-model')
        self.assertIn('consultor contábil e financeiro', call_kwargs['messages'][0]['content'])
        self.assertEqual(call_kwargs['messages'][-1]['content'], 'Analise meu mes.')
        self.assertFalse(call_kwargs['include_reasoning'])

    @override_settings(
        GROQ_API_KEY='test-key',
        GROQ_CLASSIFICATION_MODEL='openai/gpt-oss-20b',
        GROQ_TIMEOUT_SECONDS=20,
    )
    @patch('gastos.ia.Groq')
    def test_classificacao_usa_20b_e_descarta_categoria_fora_da_lista(self, groq_mock):
        groq_mock.return_value.chat.completions.create.return_value = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=(
                            '{"suggestions": ['
                            '{"index": 0, "category_id": 7, "confidence": 0.91},'
                            '{"index": 1, "category_id": 999, "confidence": 0.99}'
                            ']}'
                        )
                    )
                )
            ]
        )

        result = classificar_descricoes(
            ['Hospedagem do site', 'Descrição desconhecida'],
            [{'id': 7, 'name': 'Sistemas'}],
        )

        self.assertEqual(result, [{'index': 0, 'category_id': 7, 'confidence': 0.91}])
        call_kwargs = groq_mock.return_value.chat.completions.create.call_args.kwargs
        self.assertEqual(call_kwargs['model'], 'openai/gpt-oss-20b')
        self.assertTrue(call_kwargs['response_format']['json_schema']['strict'])

    @override_settings(GROQ_API_KEY='')
    def test_endpoint_informa_quando_api_key_nao_esta_configurada(self):
        user = User.objects.create_user(username='ana@example.com', email='ana@example.com', password='senha12345')
        complete_profile(user)
        self.client.force_login(user)

        response = self.client.post(reverse('gastos:ai_financial_insight'))

        self.assertEqual(response.status_code, 503)
        self.assertIn('Configure API_KEY', response.json()['message'])

    def test_contexto_da_ia_inclui_objetivo_empresarial_sem_identificacao(self):
        user = User.objects.create_user(username='ana@example.com', email='ana@example.com', password='senha12345')
        business = user.businesses.get(is_default=True)
        business.business_goal = 'Aumentar a previsibilidade do caixa'
        business.save()

        contexto = ai_context_for_month(user, current_month_date())

        self.assertIn('Objetivo empresarial: Aumentar a previsibilidade do caixa', contexto)
        self.assertNotIn('ana@example.com', contexto)

    def test_usuario_pode_cadastrar_multiplas_rendas_no_mes(self):
        user = User.objects.create_user(username='ana@example.com', email='ana@example.com', password='senha12345')
        complete_profile(user)
        self.client.force_login(user)
        reference_month = current_month_date()

        for amount, income_type in [('1000.00', 'fixed'), ('500.00', 'variable')]:
            response = self.client.post(
                reverse('gastos:monthly'),
                {
                    'reference_month': reference_month.strftime('%Y-%m'),
                    'income_amount': amount,
                    'income_type': income_type,
                },
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            FinancialTransaction.objects.filter(
                business__owner=user,
                direction=FinancialTransaction.Direction.INFLOW,
                date=reference_month,
            ).count(),
            2,
        )

    def test_cadastro_de_renda_nao_altera_registro_legado(self):
        user = User.objects.create_user(username='ana@example.com', email='ana@example.com', password='senha12345')
        complete_profile(user)
        self.client.force_login(user)
        reference_month = current_month_date()
        income = MonthlyIncome.objects.create(
            user=user,
            reference_month=reference_month,
            amount='1000.00',
            income_type='fixed',
        )

        response = self.client.post(
            reverse('gastos:monthly'),
            {
                'reference_month': reference_month.strftime('%Y-%m'),
                'income_amount': '500.00',
                'income_type': 'variable',
            },
        )

        income.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(str(income.amount), '1000.00')
        self.assertEqual(MonthlyIncome.objects.filter(user=user, reference_month=reference_month).count(), 1)
        transaction = FinancialTransaction.objects.get(
            business__owner=user,
            direction=FinancialTransaction.Direction.INFLOW,
        )
        self.assertEqual(transaction.amount, Decimal('500.00'))
