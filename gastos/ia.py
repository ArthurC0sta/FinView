from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from groq import Groq


SYSTEM_PROMPT = """
Voce e o assistente financeiro do FinView AI.
Responda em portugues do Brasil, com tom direto e util.
Use somente os dados financeiros enviados pelo sistema.
Sempre relacione a analise ao objetivo financeiro do usuario quando ele for informado.
Responda em topicos curtos, sem texto corrido longo.
Se os dados forem insuficientes, diga o que falta cadastrar.
Evite prometer resultados e nao trate isso como consultoria financeira profissional.
""".strip()


def groq_configured():
    return bool(settings.GROQ_API_KEY)


def groq_client():
    if not groq_configured():
        raise ImproperlyConfigured('Configure API_KEY ou GROQ_API_KEY no arquivo .env.')
    return Groq(api_key=settings.GROQ_API_KEY)


def gerar_resposta_financeira(prompt, contexto='', *, model=None, max_tokens=450):
    prompt = (prompt or '').strip()
    contexto = (contexto or '').strip()
    if not prompt:
        raise ValueError('Informe uma pergunta para a IA.')

    messages = [
        {'role': 'system', 'content': SYSTEM_PROMPT},
    ]
    if contexto:
        messages.append({'role': 'system', 'content': f'Dados do usuario:\n{contexto}'})
    messages.append({'role': 'user', 'content': prompt})

    completion = groq_client().chat.completions.create(
        model=model or settings.GROQ_MODEL,
        messages=messages,
        temperature=0.4,
        max_completion_tokens=max_tokens,
        top_p=1,
    )
    content = completion.choices[0].message.content
    return (content or '').strip()
