from decimal import Decimal

from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import PasswordResetForm, SetPasswordForm, UserCreationForm
from django.contrib.auth.models import User
from django.utils import timezone

from .models import Business, FinancialGoal, ImportRow, ManagerialCategory


class LoginForm(forms.Form):
    email = forms.EmailField(
        label='E-mail',
        widget=forms.EmailInput(attrs={'class': 'input', 'autocomplete': 'email', 'autofocus': True}),
    )
    password = forms.CharField(
        label='Senha',
        strip=False,
        widget=forms.PasswordInput(attrs={'class': 'input', 'autocomplete': 'current-password'}),
    )

    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        self.user_cache = None
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        email = (cleaned.get('email') or '').strip().lower()
        password = cleaned.get('password')
        if email and password:
            self.user_cache = authenticate(self.request, username=email, password=password)
            if self.user_cache is None:
                raise forms.ValidationError('E-mail ou senha inválidos.')
        return cleaned

    def get_user(self):
        return self.user_cache


class SignupForm(UserCreationForm):
    name = forms.CharField(label='Nome completo', max_length=150)
    email = forms.EmailField(label='E-mail')

    class Meta:
        model = User
        fields = ('name', 'email', 'password1', 'password2')

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exists() or User.objects.filter(username__iexact=email).exists():
            raise forms.ValidationError('Já existe uma conta com esse e-mail.')
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        name = self.cleaned_data['name'].strip()
        first_name, _, last_name = name.partition(' ')
        user.username = self.cleaned_data['email']
        user.email = self.cleaned_data['email']
        user.first_name = first_name
        user.last_name = last_name
        if commit:
            user.save()
        return user


class BusinessOnboardingForm(forms.ModelForm):
    class Meta:
        model = Business
        fields = (
            'name', 'segment', 'activity', 'city', 'state', 'legal_form',
            'offering_type', 'tax_regime', 'employees_count', 'business_goal',
        )
        labels = {
            'name': 'Nome da empresa', 'segment': 'Segmento', 'activity': 'Atividade principal',
            'city': 'Município', 'state': 'UF', 'legal_form': 'Enquadramento informado',
            'offering_type': 'Forma de atuação', 'tax_regime': 'Regime tributário (se conhecido)',
            'employees_count': 'Quantidade de empregados', 'business_goal': 'Objetivo empresarial',
        }
        widgets = {
            'name': forms.TextInput(attrs={'class': 'input'}),
            'segment': forms.TextInput(attrs={'class': 'input'}),
            'activity': forms.TextInput(attrs={'class': 'input'}),
            'city': forms.TextInput(attrs={'class': 'input'}),
            'state': forms.TextInput(attrs={'class': 'input', 'maxlength': 2}),
            'legal_form': forms.Select(attrs={'class': 'select'}),
            'offering_type': forms.Select(attrs={'class': 'select'}),
            'tax_regime': forms.TextInput(attrs={'class': 'input'}),
            'employees_count': forms.NumberInput(attrs={'class': 'input', 'min': 0}),
            'business_goal': forms.TextInput(attrs={'class': 'input'}),
        }

    def clean_state(self):
        return self.cleaned_data.get('state', '').strip().upper()


PROFILE_CHOICES = [
    ('0', 'Inicial'),
    ('1', 'Intermediário'),
    ('2', 'Estruturado'),
    ('unknown', 'Não sei informar'),
]


class MaturityProfileForm(forms.Form):
    records = forms.ChoiceField(label='Como o negócio registra entradas e saídas?', choices=PROFILE_CHOICES)
    update_frequency = forms.ChoiceField(label='Com que frequência os dados são atualizados?', choices=PROFILE_CHOICES)
    monthly_volume = forms.ChoiceField(label='Qual é o volume mensal de movimentações?', choices=PROFILE_CHOICES)
    future_commitments = forms.ChoiceField(label='Como são controladas contas a pagar e receber?', choices=PROFILE_CHOICES)
    people_involved = forms.ChoiceField(label='Quem participa da gestão financeira?', choices=PROFILE_CHOICES)
    predictability = forms.ChoiceField(label='Quanto o negócio consegue prever suas receitas?', choices=PROFILE_CHOICES)
    management_need = forms.ChoiceField(label='Qual é a principal necessidade atual?', choices=PROFILE_CHOICES)
    advanced_controls = forms.ChoiceField(label='Quais controles avançados são necessários?', choices=PROFILE_CHOICES)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'select'


class ProfilePreferencesForm(forms.Form):
    language = forms.ChoiceField(choices=[('simple', 'Simples'), ('balanced', 'Equilibrada'), ('technical', 'Técnica')], required=False)
    detail = forms.ChoiceField(choices=[('summary', 'Resumo'), ('balanced', 'Equilibrado'), ('detailed', 'Detalhado')], required=False)
    focus = forms.ChoiceField(choices=[('cash', 'Proteção do caixa'), ('balance', 'Equilíbrio'), ('growth', 'Crescimento')], required=False)
    frequency = forms.ChoiceField(choices=[('weekly', 'Semanal'), ('biweekly', 'Quinzenal'), ('monthly', 'Mensal')], required=False)
    alerts = forms.ChoiceField(choices=[('immediate', 'Imediatos'), ('digest', 'Resumo periódico')], required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'select'


class ImportUploadForm(forms.Form):
    file = forms.FileField(
        label='Arquivo financeiro',
        widget=forms.ClearableFileInput(attrs={'class': 'input', 'accept': '.ofx,.ofc,.csv,.xls,.pdf,.cnab,.ret'}),
    )
    sheet_name = forms.CharField(label='Aba do XLS', required=False, widget=forms.TextInput(attrs={'class': 'input', 'placeholder': 'Primeira aba'}))
    date_column = forms.CharField(label='Coluna de data', initial='data', required=False, widget=forms.TextInput(attrs={'class': 'input'}))
    description_column = forms.CharField(label='Coluna de descrição', initial='descricao', required=False, widget=forms.TextInput(attrs={'class': 'input'}))
    amount_column = forms.CharField(label='Coluna de valor', initial='valor', required=False, widget=forms.TextInput(attrs={'class': 'input'}))
    direction_column = forms.CharField(label='Coluna de natureza', initial='natureza', required=False, widget=forms.TextInput(attrs={'class': 'input'}))


class ImportRowReviewForm(forms.ModelForm):
    class Meta:
        model = ImportRow
        fields = ('decision', 'confirmed_category')
        widgets = {'decision': forms.Select(attrs={'class': 'select'}), 'confirmed_category': forms.Select(attrs={'class': 'select'})}

    def __init__(self, *args, business=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['confirmed_category'].queryset = ManagerialCategory.objects.filter(
            business=business,
            is_active=True,
        ) if business else ManagerialCategory.objects.none()
        self.fields['confirmed_category'].required = False


class FinViewPasswordResetForm(PasswordResetForm):
    """Adapta o formulario nativo de recuperacao ao visual do FinView."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].widget.attrs.update(
            {
                'class': 'input',
                'placeholder': 'voce@email.com',
                'autocomplete': 'email',
                'autocapitalize': 'none',
                'spellcheck': 'false',
                'autofocus': True,
            }
        )


class FinViewSetPasswordForm(SetPasswordForm):
    """Mantem as validacoes do Django com os campos visuais do projeto."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update(
                {
                    'class': 'input',
                    'autocomplete': 'new-password',
                    'placeholder': '••••••••',
                }
            )


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
