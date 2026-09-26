from decimal import Decimal, ROUND_HALF_UP
import uuid

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    goal = models.CharField(max_length=80, default='Controlar gastos')

    def __str__(self):
        return self.user.email or self.user.username


class Business(models.Model):
    class LegalForm(models.TextChoices):
        INFORMAL = 'informal', 'Ainda não formalizado'
        AUTONOMOUS = 'autonomous', 'Autônomo'
        MEI = 'mei', 'MEI'
        MICRO = 'micro', 'Microempresa'
        OTHER = 'other', 'Outro'

    class OfferingType(models.TextChoices):
        SERVICES = 'services', 'Serviços'
        PRODUCTS = 'products', 'Produtos'
        BOTH = 'both', 'Produtos e serviços'

    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='businesses')
    name = models.CharField(max_length=120)
    is_default = models.BooleanField(default=True)
    segment = models.CharField(max_length=120, blank=True)
    activity = models.CharField(max_length=160, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=2, blank=True)
    legal_form = models.CharField(max_length=20, choices=LegalForm.choices, blank=True)
    offering_type = models.CharField(max_length=20, choices=OfferingType.choices, blank=True)
    tax_regime = models.CharField(max_length=80, blank=True)
    employees_count = models.PositiveIntegerField(blank=True, null=True)
    business_goal = models.CharField(max_length=180, blank=True)
    profile_updated_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['owner'],
                condition=models.Q(is_default=True),
                name='one_default_business_per_owner',
            ),
        ]

    def __str__(self):
        return self.name


class ManagerialCategory(models.Model):
    class Group(models.TextChoices):
        REVENUE = 'revenue', 'Receitas'
        TAXES_FEES = 'taxes_fees', 'Impostos e taxas'
        VARIABLE_DIRECT = 'variable_direct', 'Custos variáveis e diretos'
        FIXED = 'fixed', 'Custos e despesas fixas'
        ADMINISTRATIVE = 'administrative', 'Despesas administrativas e comerciais'
        INVESTMENT = 'investment', 'Investimentos'
        LOAN = 'loan', 'Empréstimos'
        CONTRIBUTION = 'contribution', 'Aportes'
        WITHDRAWAL = 'withdrawal', 'Retiradas'
        TRANSFER = 'transfer', 'Transferências'
        UNCLASSIFIED = 'unclassified', 'Não classificadas'

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='categories')
    name = models.CharField(max_length=80)
    group = models.CharField(max_length=30, choices=Group.choices, default=Group.UNCLASSIFIED)
    is_active = models.BooleanField(default=True)
    is_system = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['business', 'name'],
                name='unique_category_name_per_business',
            ),
        ]

    def __str__(self):
        return self.name


class FinancialTransaction(models.Model):
    class Direction(models.TextChoices):
        INFLOW = 'inflow', 'Entrada'
        OUTFLOW = 'outflow', 'Saída'

    class Status(models.TextChoices):
        REALIZED = 'realized', 'Realizado'
        PLANNED = 'planned', 'Previsto'

    class Certainty(models.TextChoices):
        CONFIRMED = 'confirmed', 'Confirmado'
        ESTIMATED = 'estimated', 'Estimado'

    class Source(models.TextChoices):
        MANUAL = 'manual', 'Manual'
        MIGRATION = 'migration', 'Migração'
        RECURRENCE = 'recurrence', 'Recorrência'
        IMPORT = 'import', 'Importação'

    RECURRENCE_CHOICES = [
        ('fixed', 'Fixa'),
        ('variable', 'Variável'),
    ]
    PRIORITY_CHOICES = [
        ('essential', 'Essencial'),
        ('important', 'Importante'),
        ('superfluous', 'Dispensável'),
    ]

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='transactions')
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name='created_financial_transactions',
        blank=True,
        null=True,
    )
    direction = models.CharField(max_length=10, choices=Direction.choices)
    name = models.CharField(max_length=120)
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    date = models.DateField()
    category = models.ForeignKey(
        ManagerialCategory,
        on_delete=models.PROTECT,
        related_name='transactions',
    )
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.REALIZED)
    certainty = models.CharField(max_length=12, choices=Certainty.choices, default=Certainty.CONFIRMED)
    recurrence = models.CharField(max_length=20, choices=RECURRENCE_CHOICES, default='variable')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='essential')
    source = models.CharField(max_length=12, choices=Source.choices, default=Source.MANUAL)
    notes = models.TextField(blank=True)
    legacy_income_id = models.PositiveBigIntegerField(blank=True, null=True, unique=True)
    legacy_expense_id = models.PositiveBigIntegerField(blank=True, null=True, unique=True)
    import_row = models.OneToOneField(
        'ImportRow',
        on_delete=models.SET_NULL,
        related_name='transaction',
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name='financial_transaction_amount_positive',
            ),
        ]
        indexes = [
            models.Index(fields=['business', 'date'], name='fin_tx_business_date_idx'),
            models.Index(fields=['business', 'direction', 'date'], name='fin_tx_direction_date_idx'),
        ]

    def __str__(self):
        return f'{self.name} - {self.amount}'

    @property
    def amount_display(self):
        value = f'{self.amount:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
        return f'R$ {value}'


class BusinessProfileAssessment(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Rascunho'
        COMPLETED = 'completed', 'Concluída'

    class Level(models.TextChoices):
        ESSENTIAL = 'essential', 'Essencial'
        MANAGERIAL = 'managerial', 'Gerencial'
        COMPLETE = 'complete', 'Completa'

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='profile_assessments')
    questionnaire_version = models.CharField(max_length=20, default='1.0')
    maturity_answers = models.JSONField(default=dict, blank=True)
    preferences = models.JSONField(default=dict, blank=True)
    score = models.PositiveSmallIntegerField(blank=True, null=True)
    recommended_level = models.CharField(max_length=20, choices=Level.choices, blank=True)
    determining_factors = models.JSONField(default=list, blank=True)
    is_boundary = models.BooleanField(default=False)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    is_current = models.BooleanField(default=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['business'],
                condition=models.Q(is_current=True),
                name='one_current_profile_assessment_per_business',
            ),
        ]


def private_import_path(instance, filename):
    suffix = filename.rsplit('.', 1)[-1].lower() if '.' in filename else 'bin'
    return f'imports/{instance.business_id}/{instance.public_id}.{suffix}'


class ImportBatch(models.Model):
    class Format(models.TextChoices):
        CSV = 'csv', 'CSV'
        XLS = 'xls', 'XLS'
        OFX = 'ofx', 'OFX/OFC'
        PDF = 'pdf', 'PDF'
        CNAB = 'cnab', 'CNAB'

    class Status(models.TextChoices):
        RECEIVED = 'received', 'Recebido'
        VALIDATING = 'validating', 'Validando'
        AWAITING_REVIEW = 'awaiting_review', 'Aguardando revisão'
        CONFIRMED = 'confirmed', 'Confirmado'
        PROCESSED = 'processed', 'Processado'
        PARTIALLY_PROCESSED = 'partially_processed', 'Processado parcialmente'
        REJECTED = 'rejected', 'Rejeitado'
        CANCELLED = 'cancelled', 'Cancelado'
        EXPIRED = 'expired', 'Expirado'

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='import_batches')
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='import_batches')
    original_name = models.CharField(max_length=255)
    file_format = models.CharField(max_length=10, choices=Format.choices)
    file_hash = models.CharField(max_length=64)
    file_size = models.PositiveIntegerField()
    stored_file = models.FileField(upload_to=private_import_path, blank=True)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.RECEIVED)
    total_rows = models.PositiveIntegerField(default=0)
    valid_rows = models.PositiveIntegerField(default=0)
    invalid_rows = models.PositiveIntegerField(default=0)
    duplicate_rows = models.PositiveIntegerField(default=0)
    error_code = models.CharField(max_length=60, blank=True)
    error_message = models.CharField(max_length=240, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    finalized_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['business', 'file_hash'],
                name='unique_import_file_per_business',
            ),
        ]


class ImportRow(models.Model):
    class ValidationStatus(models.TextChoices):
        VALID = 'valid', 'Válida'
        INVALID = 'invalid', 'Inválida'
        INCOMPLETE = 'incomplete', 'Incompleta'

    class Decision(models.TextChoices):
        PENDING = 'pending', 'Pendente'
        INCLUDE = 'include', 'Incluir'
        IGNORE = 'ignore', 'Ignorar'

    batch = models.ForeignKey(ImportBatch, on_delete=models.CASCADE, related_name='rows')
    row_number = models.PositiveIntegerField()
    date = models.DateField(blank=True, null=True)
    description = models.CharField(max_length=240, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    direction = models.CharField(max_length=10, choices=FinancialTransaction.Direction.choices, blank=True)
    external_identifier = models.CharField(max_length=160, blank=True)
    fingerprint = models.CharField(max_length=64)
    validation_status = models.CharField(
        max_length=12,
        choices=ValidationStatus.choices,
        default=ValidationStatus.INCOMPLETE,
    )
    validation_errors = models.JSONField(default=list, blank=True)
    possible_duplicate = models.BooleanField(default=False)
    suggested_category = models.ForeignKey(
        ManagerialCategory,
        on_delete=models.SET_NULL,
        related_name='suggested_import_rows',
        blank=True,
        null=True,
    )
    classification_confidence = models.DecimalField(max_digits=4, decimal_places=3, blank=True, null=True)
    confirmed_category = models.ForeignKey(
        ManagerialCategory,
        on_delete=models.SET_NULL,
        related_name='confirmed_import_rows',
        blank=True,
        null=True,
    )
    decision = models.CharField(max_length=10, choices=Decision.choices, default=Decision.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['row_number', 'id']
        constraints = [
            models.UniqueConstraint(fields=['batch', 'row_number'], name='unique_row_number_per_import'),
        ]


class MonthlyIncome(models.Model):
    INCOME_TYPES = [
        ('fixed', 'Salário fixo'),
        ('variable', 'Freelance / Variável'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='monthly_incomes')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    income_type = models.CharField(max_length=20, choices=INCOME_TYPES, default='fixed')
    reference_month = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-reference_month']

    def __str__(self):
        return f'{self.user.email} - {self.reference_month:%Y-%m}'


class Expense(models.Model):
    RECURRENCE_CHOICES = [
        ('fixed', 'Fixa'),
        ('variable', 'Variável'),
    ]
    PRIORITY_CHOICES = [
        ('essential', 'Essencial'),
        ('important', 'Importante'),
        ('superfluous', 'Dispensável'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='expenses')
    name = models.CharField(max_length=120)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateField()
    category = models.CharField(max_length=60)
    recurrence = models.CharField(max_length=20, choices=RECURRENCE_CHOICES, default='variable')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='essential')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f'{self.name} - {self.amount}'

    @property
    def amount_display(self):
        value = f'{self.amount:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
        return f'R$ {value}'


class FinancialGoal(models.Model):
    GOAL_TYPES = [
        ('saving', 'Economia'),
        ('debt', 'Quitar dívida'),
        ('investment', 'Investimento'),
        ('purchase', 'Compra'),
        ('emergency', 'Reserva de emergência'),
    ]
    PRIORITY_CHOICES = [
        ('low', 'Baixa'),
        ('medium', 'Média'),
        ('high', 'Alta'),
    ]
    STATUS_CHOICES = [
        ('active', 'Ativa'),
        ('paused', 'Pausada'),
        ('completed', 'Concluída'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='financial_goals')
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name='financial_goals',
        blank=True,
        null=True,
    )
    name = models.CharField(max_length=120)
    target_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    saved_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    target_date = models.DateField(blank=True, null=True)
    goal_type = models.CharField(max_length=20, choices=GOAL_TYPES, default='saving')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(target_amount__gt=0),
                name='financial_goal_target_positive',
            ),
            models.CheckConstraint(
                condition=models.Q(saved_amount__gte=0),
                name='financial_goal_saved_nonnegative',
            ),
            models.CheckConstraint(
                condition=models.Q(saved_amount__lte=models.F('target_amount')),
                name='financial_goal_saved_lte_target',
            ),
        ]

    def __str__(self):
        return f'{self.user.email} - {self.name}'

    def save(self, *args, **kwargs):
        if self.business_id is None and self.user_id is not None:
            business, _ = Business.objects.get_or_create(
                owner_id=self.user_id,
                is_default=True,
                defaults={'name': f'Negócio de {self.user.email or self.user.username}'},
            )
            self.business = business
        super().save(*args, **kwargs)

    def clean(self):
        errors = {}
        if self.target_amount is not None and self.target_amount <= 0:
            errors['target_amount'] = 'O valor alvo deve ser maior que zero.'
        if self.saved_amount is not None and self.saved_amount < 0:
            errors['saved_amount'] = 'O valor guardado não pode ser negativo.'
        if (
            self.target_amount is not None
            and self.saved_amount is not None
            and self.saved_amount > self.target_amount
        ):
            errors['saved_amount'] = 'O valor guardado não pode ser maior que o valor alvo.'
        if self.target_date and self._state.adding and self.target_date < timezone.localdate():
            errors['target_date'] = 'O prazo não pode estar no passado.'
        if errors:
            raise ValidationError(errors)

    @property
    def remaining_amount(self):
        return max(self.target_amount - self.saved_amount, Decimal('0.00'))

    @property
    def progress_percent(self):
        if not self.target_amount or self.target_amount <= 0:
            return 0
        progress = int((self.saved_amount / self.target_amount) * 100)
        return max(0, min(progress, 100))

    @property
    def months_remaining(self):
        if not self.target_date:
            return None
        today = timezone.localdate()
        month_difference = (self.target_date.year - today.year) * 12 + self.target_date.month - today.month
        return max(month_difference, 1)

    @property
    def required_monthly_amount(self):
        if self.months_remaining is None:
            return None
        return (self.remaining_amount / self.months_remaining).quantize(
            Decimal('0.01'),
            rounding=ROUND_HALF_UP,
        )

    @property
    def is_completed(self):
        return self.remaining_amount == 0 or self.status == 'completed'


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)
        Business.objects.create(
            owner=instance,
            name=f'Negócio de {instance.get_full_name() or instance.email or instance.username}',
            is_default=True,
        )
