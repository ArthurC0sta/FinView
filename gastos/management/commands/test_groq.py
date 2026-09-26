from time import monotonic

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from gastos.ia import gerar_resposta_financeira, groq_configured


class Command(BaseCommand):
    help = 'Executa smoke tests sanitizados nos modelos Groq configurados.'

    def handle(self, *args, **options):
        if not groq_configured():
            raise CommandError('GROQ_API_KEY ou API_KEY não está configurada.')

        checks = (
            ('analysis', settings.GROQ_ANALYSIS_MODEL, 'Responda somente: analise-ok'),
            ('classification', settings.GROQ_CLASSIFICATION_MODEL, 'Responda somente: classificacao-ok'),
        )
        for purpose, model, prompt in checks:
            started = monotonic()
            response = gerar_resposta_financeira(
                prompt,
                purpose=purpose,
                model=model,
                max_tokens=160,
            )
            elapsed_ms = int((monotonic() - started) * 1000)
            if not response:
                raise CommandError(f'{model}: resposta vazia.')
            self.stdout.write(self.style.SUCCESS(f'{model}: OK ({elapsed_ms} ms)'))
