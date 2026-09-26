from functools import lru_cache
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

import json

from groq import Groq, NotFoundError


SKILL_PROMPT_RELATIVE_PATH = Path(
    'skills/consultor-contabil-pequenos-negocios/references/prompt-api.md'
)


@lru_cache(maxsize=1)
def carregar_prompt_consultor():
    """Carrega a versão da skill destinada ao modelo chamado pela API."""
    configured_path = getattr(settings, 'FINVIEW_ACCOUNTING_SKILL_PROMPT_PATH', '')
    prompt_path = Path(configured_path) if configured_path else settings.BASE_DIR / SKILL_PROMPT_RELATIVE_PATH

    try:
        prompt = prompt_path.read_text(encoding='utf-8').strip()
    except OSError as exc:
        raise ImproperlyConfigured(
            f'Prompt da skill contábil não encontrado em {prompt_path}.'
        ) from exc

    if not prompt:
        raise ImproperlyConfigured('O prompt da skill contábil está vazio.')
    return prompt


def groq_configured():
    return bool(settings.GROQ_API_KEY)


def groq_client():
    if not groq_configured():
        raise ImproperlyConfigured('Configure API_KEY ou GROQ_API_KEY no arquivo .env.')
    return Groq(
        api_key=settings.GROQ_API_KEY,
        timeout=settings.GROQ_TIMEOUT_SECONDS,
        max_retries=1,
    )


def model_for_purpose(purpose):
    if purpose == 'classification':
        return settings.GROQ_CLASSIFICATION_MODEL
    return settings.GROQ_ANALYSIS_MODEL


def gerar_resposta_financeira(
    prompt,
    contexto='',
    *,
    model=None,
    purpose='analysis',
    max_tokens=450,
):
    prompt = (prompt or '').strip()
    contexto = (contexto or '').strip()
    if not prompt:
        raise ValueError('Informe uma pergunta para a IA.')

    messages = [
        {'role': 'system', 'content': carregar_prompt_consultor()},
    ]
    if contexto:
        messages.append({'role': 'system', 'content': f'Contexto financeiro anonimizado:\n{contexto}'})
    messages.append({'role': 'user', 'content': prompt})

    selected_model = model or model_for_purpose(purpose)
    client = groq_client()
    request = {
        'model': selected_model,
        'messages': messages,
        'temperature': 0.4,
        'max_completion_tokens': max_tokens,
        'top_p': 1,
        'include_reasoning': False,
    }
    try:
        completion = client.chat.completions.create(**request)
    except NotFoundError:
        if purpose != 'analysis' or selected_model == settings.GROQ_CLASSIFICATION_MODEL:
            raise
        request['model'] = settings.GROQ_CLASSIFICATION_MODEL
        completion = client.chat.completions.create(**request)
    content = completion.choices[0].message.content
    return (content or '').strip()


def classificar_descricoes(descriptions, categories):
    """Sugere categorias sem persistir ou enviar dados identificáveis."""
    clean_descriptions = [str(item).strip()[:180] for item in descriptions if str(item).strip()]
    allowed_categories = [
        {'id': int(item['id']), 'name': str(item['name'])[:80]}
        for item in categories
    ]
    if not clean_descriptions or not allowed_categories:
        return []

    item_schema = {
        'type': 'object',
        'properties': {
            'index': {'type': 'integer'},
            'category_id': {'type': 'integer'},
            'confidence': {'type': 'number'},
        },
        'required': ['index', 'category_id', 'confidence'],
        'additionalProperties': False,
    }
    schema = {
        'type': 'object',
        'properties': {'suggestions': {'type': 'array', 'items': item_schema}},
        'required': ['suggestions'],
        'additionalProperties': False,
    }
    completion = groq_client().chat.completions.create(
        model=model_for_purpose('classification'),
        messages=[
            {
                'role': 'user',
                'content': (
                    'Classifique cada descrição usando somente os IDs permitidos. '
                    f'Descrições: {clean_descriptions}. Categorias: {allowed_categories}.'
                ),
            }
        ],
        response_format={
            'type': 'json_schema',
            'json_schema': {
                'name': 'transaction_classification',
                'strict': True,
                'schema': schema,
            },
        },
        temperature=0,
        max_completion_tokens=1200,
        include_reasoning=False,
    )
    data = json.loads(completion.choices[0].message.content or '{}')
    allowed_ids = {item['id'] for item in allowed_categories}
    valid = []
    for suggestion in data.get('suggestions', []):
        index = suggestion.get('index')
        category_id = suggestion.get('category_id')
        confidence = suggestion.get('confidence')
        if (
            isinstance(index, int)
            and 0 <= index < len(clean_descriptions)
            and category_id in allowed_ids
            and isinstance(confidence, (int, float))
        ):
            valid.append(
                {
                    'index': index,
                    'category_id': category_id,
                    'confidence': max(0, min(float(confidence), 1)),
                }
            )
    return valid
