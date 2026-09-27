# Desenvolvimento do FinView

O produto oficial é a aplicação Django na raiz do repositório. `sites-app/` e `design-lab/` são referências históricas e não devem ser usados para validar a interface oficial.

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

## Migração de um snapshot do Sites

O comando abaixo aceita um JSON exportado do D1 com as chaves `users`, `businesses`, `managerial_categories`, `financial_transactions`, `financial_goals`, `business_profile_assessments`, `import_batches` e `import_rows`.

```bash
python manage.py import_sites_snapshot snapshot.json --dry-run
python manage.py import_sites_snapshot snapshot.json --send-password-reset
```

Sempre execute primeiro com `--dry-run` e compare contagens e totais antes da importação real. O comando registra IDs externos para impedir duplicação em uma nova execução.
