# Desenvolvimento do FinView

O produto oficial é a aplicação Django na raiz do repositório. `design-lab/` é apenas uma referência histórica e não deve ser usado para validar a interface oficial.

## Execução local

```bash
source .venv/bin/activate
python manage.py migrate
python manage.py runserver
```

Acesse `http://127.0.0.1:8000/`. Antes de entregar uma mudança, execute:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python manage.py check
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python manage.py makemigrations --check --dry-run
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python manage.py test
git diff --check
```
