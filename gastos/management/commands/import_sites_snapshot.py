import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from gastos.models import (
    Business, BusinessProfileAssessment, ExternalMigrationRecord, FinancialGoal,
    FinancialTransaction, ImportBatch, ImportRow, ManagerialCategory,
)


def value(row, *names, default=None):
    for name in names:
        if name in row and row[name] is not None:
            return row[name]
    return default


def money_from_cents(row, cents_name, decimal_name):
    cents = value(row, cents_name)
    if cents is not None:
        return (Decimal(str(cents)) / 100).quantize(Decimal('0.01'))
    return Decimal(str(value(row, decimal_name, default='0'))).quantize(Decimal('0.01'))


class Command(BaseCommand):
    help = 'Importa um snapshot JSON sanitizado do Sites/D1 de forma idempotente.'

    def add_arguments(self, parser):
        parser.add_argument('snapshot', type=Path)
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--send-password-reset', action='store_true')

    def handle(self, *args, **options):
        path = options['snapshot']
        try:
            payload = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError) as exc:
            raise CommandError(f'Snapshot inválido: {exc}') from exc
        required = {'users', 'businesses', 'managerial_categories', 'financial_transactions', 'financial_goals', 'business_profile_assessments', 'import_batches', 'import_rows'}
        missing = required.difference(payload)
        if missing:
            raise CommandError(f'Tabelas ausentes: {", ".join(sorted(missing))}.')

        counters = {name: 0 for name in required}
        reset_emails = []
        with transaction.atomic():
            users = {}
            for row in payload['users']:
                external_id = str(value(row, 'id', default=''))
                email = str(value(row, 'email', default='')).strip().lower()
                if not external_id or not email:
                    raise CommandError('Usuário sem id ou e-mail.')
                user, created = User.objects.get_or_create(username=email, defaults={'email': email})
                if created:
                    user.set_unusable_password()
                    user.save(update_fields=['password'])
                    reset_emails.append(email)
                    counters['users'] += 1
                self._record('users', external_id, user)
                users[external_id] = user

            businesses = {}
            for row in payload['businesses']:
                external_id = str(value(row, 'id', default=''))
                owner = users.get(str(value(row, 'owner_user_id', 'ownerUserId', 'user_id')))
                if not owner:
                    raise CommandError(f'Empresa {external_id} sem proprietário conhecido.')
                business, created = Business.objects.get_or_create(
                    owner=owner, is_default=True,
                    defaults={'name': value(row, 'name', default=f'Negócio de {owner.email}')},
                )
                for field, names in {
                    'name': ('name',), 'segment': ('segment',), 'activity': ('activity',),
                    'city': ('city',), 'state': ('state',), 'business_goal': ('business_goal', 'businessGoal'),
                }.items():
                    setattr(business, field, str(value(row, *names, default=getattr(business, field, '')) or ''))
                business.save()
                counters['businesses'] += int(created)
                self._record('businesses', external_id, business)
                businesses[external_id] = business

            categories = {}
            for row in payload['managerial_categories']:
                external_id = str(value(row, 'id', default=''))
                business = businesses.get(str(value(row, 'business_id', 'businessId')))
                if not business:
                    raise CommandError(f'Categoria {external_id} sem empresa conhecida.')
                category, created = ManagerialCategory.objects.get_or_create(
                    business=business, name=str(value(row, 'name', default='Não classificadas'))[:80],
                    defaults={'group': value(row, 'group_name', 'groupName', 'group', default='unclassified')},
                )
                counters['managerial_categories'] += int(created)
                self._record('managerial_categories', external_id, category)
                categories[external_id] = category

            for row in payload['financial_transactions']:
                external_id = str(value(row, 'id', default=''))
                if self._exists('financial_transactions', external_id):
                    continue
                business = businesses[str(value(row, 'business_id', 'businessId'))]
                category = categories[str(value(row, 'category_id', 'categoryId'))]
                obj = FinancialTransaction.objects.create(
                    business=business, created_by=business.owner,
                    direction=value(row, 'direction'), name=str(value(row, 'name', default='Movimentação'))[:120],
                    amount=money_from_cents(row, 'amount_cents', 'amount'),
                    date=date.fromisoformat(value(row, 'transaction_date', 'date')),
                    category=category, status=value(row, 'status', default='realized'),
                    certainty=value(row, 'certainty', default='confirmed'), source=FinancialTransaction.Source.MIGRATION,
                )
                counters['financial_transactions'] += 1
                self._record('financial_transactions', external_id, obj)

            for row in payload['financial_goals']:
                external_id = str(value(row, 'id', default=''))
                if self._exists('financial_goals', external_id):
                    continue
                business = businesses[str(value(row, 'business_id', 'businessId'))]
                target_date = value(row, 'target_date', 'targetDate')
                obj = FinancialGoal.objects.create(
                    user=business.owner, business=business, name=str(value(row, 'name', default='Meta'))[:120],
                    target_amount=money_from_cents(row, 'target_amount_cents', 'target_amount'),
                    saved_amount=money_from_cents(row, 'saved_amount_cents', 'saved_amount'),
                    target_date=date.fromisoformat(target_date) if target_date else None,
                    goal_type=value(row, 'goal_type', 'goalType', default='saving'),
                    priority=value(row, 'priority', default='medium'), status=value(row, 'status', default='active'),
                )
                counters['financial_goals'] += 1
                self._record('financial_goals', external_id, obj)

            for row in payload['business_profile_assessments']:
                external_id = str(value(row, 'id', default=''))
                if self._exists('business_profile_assessments', external_id):
                    continue
                business = businesses[str(value(row, 'business_id', 'businessId'))]
                BusinessProfileAssessment.objects.filter(business=business, is_current=True).update(is_current=False)
                recommended = value(row, 'recommended_level', 'recommendedLevel', default='')
                obj = BusinessProfileAssessment.objects.create(
                    business=business, questionnaire_version=str(value(row, 'questionnaire_version', 'questionnaireVersion', default='sites-1')),
                    maturity_answers=value(row, 'maturity_answers', 'maturityAnswers', default={}),
                    preferences={key: val for key, val in value(row, 'preferences', default={}).items() if key != 'focus'},
                    score=value(row, 'score'), recommended_level=recommended, selected_level=recommended,
                    status=value(row, 'status', default='completed'), is_current=True,
                )
                counters['business_profile_assessments'] += 1
                self._record('business_profile_assessments', external_id, obj)

            batches = {}
            for row in payload['import_batches']:
                external_id = str(value(row, 'id', default=''))
                business = businesses[str(value(row, 'business_id', 'businessId'))]
                ledger = ExternalMigrationRecord.objects.filter(source='sites-d1', entity='import_batches', external_id=external_id).first()
                if ledger:
                    batches[external_id] = ImportBatch.objects.get(pk=ledger.local_id)
                    continue
                obj = ImportBatch.objects.create(
                    business=business, uploaded_by=business.owner,
                    original_name=str(value(row, 'original_name', 'originalName', default='arquivo-importado'))[:255],
                    file_format=value(row, 'file_format', 'fileFormat', default='csv'),
                    file_hash=str(value(row, 'file_hash', 'fileHash', default=external_id))[:64],
                    file_size=int(value(row, 'file_size', 'fileSize', default=0)),
                    status=value(row, 'status', default='processed'),
                    total_rows=int(value(row, 'total_rows', 'totalRows', default=0)),
                    valid_rows=int(value(row, 'valid_rows', 'validRows', default=0)),
                    invalid_rows=int(value(row, 'invalid_rows', 'invalidRows', default=0)),
                    error_message=str(value(row, 'error_message', 'errorMessage', default=''))[:240],
                )
                counters['import_batches'] += 1
                self._record('import_batches', external_id, obj)
                batches[external_id] = obj

            for row in payload['import_rows']:
                external_id = str(value(row, 'id', default=''))
                if self._exists('import_rows', external_id):
                    continue
                batch = batches[str(value(row, 'batch_id', 'batchId'))]
                suggested = categories.get(str(value(row, 'suggested_category_id', 'suggestedCategoryId', default='')))
                confirmed = categories.get(str(value(row, 'confirmed_category_id', 'confirmedCategoryId', default='')))
                row_date = value(row, 'transaction_date', 'date')
                description = str(value(row, 'description', default=''))[:240]
                obj = ImportRow.objects.create(
                    batch=batch, row_number=int(value(row, 'source_row', 'sourceRow', 'row_number', default=1)),
                    date=date.fromisoformat(row_date) if row_date else None,
                    description=description, original_description=description,
                    amount=money_from_cents(row, 'amount_cents', 'amount') if value(row, 'amount_cents', 'amount') is not None else None,
                    direction=value(row, 'direction', default=''),
                    external_identifier=str(value(row, 'external_id', 'externalId', default=''))[:160],
                    fingerprint=str(value(row, 'fingerprint', default=external_id))[:64],
                    validation_status='valid' if value(row, 'is_valid', 'isValid', default=True) else 'invalid',
                    suggested_category=suggested, confirmed_category=confirmed,
                    decision={'accepted': 'include', 'excluded': 'ignore'}.get(value(row, 'decision'), value(row, 'decision', default='pending')),
                )
                counters['import_rows'] += 1
                self._record('import_rows', external_id, obj)

            if options['dry_run']:
                transaction.set_rollback(True)

        if options['send_password_reset'] and not options['dry_run']:
            for email in reset_emails:
                form = PasswordResetForm({'email': email})
                if form.is_valid():
                    form.save(domain_override='localhost', use_https=False)
        mode = 'SIMULAÇÃO' if options['dry_run'] else 'IMPORTAÇÃO'
        self.stdout.write(self.style.SUCCESS(f'{mode} concluída: {counters}'))

    def _exists(self, entity, external_id):
        return ExternalMigrationRecord.objects.filter(source='sites-d1', entity=entity, external_id=external_id).exists()

    def _record(self, entity, external_id, obj):
        ExternalMigrationRecord.objects.get_or_create(
            source='sites-d1', entity=entity, external_id=external_id,
            defaults={'local_model': obj._meta.label_lower, 'local_id': str(obj.pk)},
        )
