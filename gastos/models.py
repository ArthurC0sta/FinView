from decimal import Decimal, ROUND_HALF_UP

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
