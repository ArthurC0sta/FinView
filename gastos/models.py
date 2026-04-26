from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    goal = models.CharField(max_length=80, default='Controlar gastos')

    def __str__(self):
        return self.user.email or self.user.username


class MonthlyIncome(models.Model):
    INCOME_TYPES = [
        ('fixed', 'Salário fixo'),
        ('variable', 'Freelance / Variável'),
        ('mixed', 'Misto'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='monthly_incomes')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    income_type = models.CharField(max_length=20, choices=INCOME_TYPES, default='fixed')
    reference_month = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'reference_month')
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
        ('superfluous', 'Supérflua'),
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


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)
