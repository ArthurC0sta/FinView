from types import SimpleNamespace

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from unittest.mock import patch

from .ia import gerar_resposta_financeira
from .views import ai_context_for_month, current_month_date


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
