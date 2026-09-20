import re
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from urllib.parse import urlparse

from django.contrib.auth.models import User
from django.core import mail
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from unittest.mock import patch

from .ia import gerar_resposta_financeira
from .models import FinancialGoal, MonthlyIncome
from .views import (
    active_goals_for_user,
    ai_context_for_month,
    current_month_date,
)


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
    @override_settings(GROQ_API_KEY='test-key', GROQ_MODEL='test-model')
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
        groq_mock.assert_called_once_with(api_key='test-key')
        groq_mock.return_value.chat.completions.create.assert_called_once()
        call_kwargs = groq_mock.return_value.chat.completions.create.call_args.kwargs
        self.assertEqual(call_kwargs['model'], 'test-model')
        self.assertEqual(call_kwargs['messages'][-1]['content'], 'Analise meu mes.')

    @override_settings(GROQ_API_KEY='')
    def test_endpoint_informa_quando_api_key_nao_esta_configurada(self):
        user = User.objects.create_user(username='ana@example.com', email='ana@example.com', password='senha12345')
        self.client.force_login(user)

        response = self.client.post(reverse('gastos:ai_financial_insight'))

        self.assertEqual(response.status_code, 503)
        self.assertIn('Configure API_KEY', response.json()['message'])

    def test_contexto_da_ia_inclui_objetivo_financeiro(self):
        user = User.objects.create_user(username='ana@example.com', email='ana@example.com', password='senha12345')
        user.profile.goal = 'Reduzir dívidas'
        user.profile.save()

        contexto = ai_context_for_month(user, current_month_date())

        self.assertIn('Objetivo financeiro: Reduzir dívidas', contexto)

    def test_usuario_pode_cadastrar_multiplas_rendas_no_mes(self):
        user = User.objects.create_user(username='ana@example.com', email='ana@example.com', password='senha12345')
        self.client.force_login(user)
        reference_month = current_month_date()

        MonthlyIncome.objects.create(
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

        self.assertEqual(response.status_code, 302)
        self.assertEqual(MonthlyIncome.objects.filter(user=user, reference_month=reference_month).count(), 2)

    def test_cadastro_de_renda_soma_valor_se_banco_ainda_tiver_restricao_unica(self):
        user = User.objects.create_user(username='ana@example.com', email='ana@example.com', password='senha12345')
        self.client.force_login(user)
        reference_month = current_month_date()
        income = MonthlyIncome.objects.create(
            user=user,
            reference_month=reference_month,
            amount='1000.00',
            income_type='fixed',
        )

        with patch('gastos.views.MonthlyIncome.objects.create', side_effect=IntegrityError('unique constraint')):
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
        self.assertEqual(str(income.amount), '1500.00')
        self.assertEqual(MonthlyIncome.objects.filter(user=user, reference_month=reference_month).count(), 1)
