from decimal import Decimal

from django import forms
from django.utils import timezone

from .models import FinancialGoal


class FinancialGoalForm(forms.ModelForm):
    def __init__(self, data=None, *args, **kwargs):
        if data is not None:
            data = data.copy()
            for field_name in ('target_amount', 'saved_amount'):
                raw_value = data.get(field_name, '')
                if isinstance(raw_value, str) and ',' in raw_value:
                    data[field_name] = raw_value.replace('.', '').replace(',', '.')
        super().__init__(data, *args, **kwargs)

    class Meta:
        model = FinancialGoal
        fields = (
            'name',
            'target_amount',
            'saved_amount',
            'target_date',
            'goal_type',
            'priority',
            'notes',
        )
        labels = {
            'name': 'Nome da meta',
            'target_amount': 'Valor alvo (R$)',
            'saved_amount': 'Valor já guardado (R$)',
            'target_date': 'Prazo desejado',
            'goal_type': 'Tipo de meta',
            'priority': 'Prioridade',
            'notes': 'Notas',
        }
        error_messages = {
            'name': {'required': 'Este campo é obrigatório.'},
            'target_amount': {
                'required': 'Este campo é obrigatório.',
                'invalid': 'Informe um valor válido.',
                'min_value': 'O valor alvo deve ser maior que zero.',
            },
            'saved_amount': {
                'invalid': 'Informe um valor válido.',
                'min_value': 'O valor guardado não pode ser negativo.',
            },
            'goal_type': {'invalid_choice': 'Faça uma escolha válida.'},
            'priority': {'invalid_choice': 'Faça uma escolha válida.'},
        }
        widgets = {
            'name': forms.TextInput(attrs={'class': 'input', 'placeholder': 'Ex: Reserva de emergência'}),
            'target_amount': forms.TextInput(
                attrs={'class': 'input money-input', 'inputmode': 'decimal', 'autocomplete': 'off'}
            ),
            'saved_amount': forms.TextInput(
                attrs={'class': 'input money-input', 'inputmode': 'decimal', 'autocomplete': 'off'}
            ),
            'target_date': forms.DateInput(attrs={'class': 'input', 'type': 'date'}, format='%Y-%m-%d'),
            'goal_type': forms.Select(attrs={'class': 'select'}),
            'priority': forms.Select(attrs={'class': 'select'}),
            'notes': forms.Textarea(
                attrs={'class': 'textarea', 'rows': 3, 'placeholder': 'Detalhes adicionais...'}
            ),
        }

    def clean_target_amount(self):
        target_amount = self.cleaned_data.get('target_amount')
        if target_amount is not None and target_amount <= Decimal('0'):
            raise forms.ValidationError('O valor alvo deve ser maior que zero.')
        return target_amount

    def clean_saved_amount(self):
        saved_amount = self.cleaned_data.get('saved_amount')
        if saved_amount is not None and saved_amount < Decimal('0'):
            raise forms.ValidationError('O valor guardado não pode ser negativo.')
        return saved_amount

    def clean_target_date(self):
        target_date = self.cleaned_data.get('target_date')
        if target_date and target_date < timezone.localdate():
            raise forms.ValidationError('O prazo não pode estar no passado.')
        return target_date

    def clean(self):
        cleaned_data = super().clean()
        target_amount = cleaned_data.get('target_amount')
        saved_amount = cleaned_data.get('saved_amount')
        if (
            target_amount is not None
            and saved_amount is not None
            and saved_amount > target_amount
        ):
            self.add_error('saved_amount', 'O valor guardado não pode ser maior que o valor alvo.')
        return cleaned_data
