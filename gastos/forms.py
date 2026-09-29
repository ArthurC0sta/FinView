from decimal import Decimal
import re

from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import PasswordResetForm, SetPasswordForm, UserCreationForm
from django.contrib.auth.models import User
from django.utils import timezone

from .models import Business, BusinessProfileAssessment, FinancialGoal, ImportRow, ManagerialCategory


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


UNKNOWN = ('unknown', 'Não sei informar')
OTHER = ('other', 'Outro cenário (descreva abaixo)')


class MaturityProfileForm(forms.Form):
    records = forms.ChoiceField(label='Como o negócio registra entradas e saídas?', choices=[('0','Não registra de forma organizada'),('1','Registra parte das movimentações'),('2','Registra todas em uma rotina definida'), UNKNOWN, OTHER])
    update_frequency = forms.ChoiceField(label='Com que frequência os dados são atualizados?', choices=[('0','Somente quando surge uma necessidade'),('1','Uma ou duas vezes por mês'),('2','Semanalmente ou com maior frequência'), UNKNOWN, OTHER])
    monthly_volume = forms.ChoiceField(label='Qual é o volume mensal de movimentações?', choices=[('0','Até 20 lançamentos'),('1','De 21 a 100 lançamentos'),('2','Mais de 100 lançamentos'), UNKNOWN, OTHER])
    future_commitments = forms.ChoiceField(label='Como são controladas contas a pagar e receber?', choices=[('0','Não há controle antecipado'),('1','Parte dos compromissos é acompanhada'),('2','Valores e vencimentos são registrados'), UNKNOWN, OTHER])
    people_involved = forms.ChoiceField(label='Quem participa da gestão financeira?', choices=[('0','Somente o proprietário, sem rotina'),('1','O proprietário com apoio eventual'),('2','Há responsáveis e rotina definida'), UNKNOWN, OTHER])
    predictability = forms.ChoiceField(label='Quanto o negócio consegue prever suas receitas?', choices=[('0','Não consegue prever'),('1','Possui uma estimativa aproximada'),('2','Acompanha previsões e confirmações'), UNKNOWN, OTHER])
    management_need = forms.ChoiceField(label='Qual é a principal necessidade atual?', choices=[('0','Organizar os dados básicos'),('1','Acompanhar caixa e compromissos'),('2','Comparar indicadores e planejar ações'), UNKNOWN, OTHER])
    advanced_controls = forms.ChoiceField(label='Quais controles avançados são necessários?', choices=[('0','Nenhum neste momento'),('1','Metas, alertas ou projeções simples'),('2','Indicadores, cenários e acompanhamento frequente'), UNKNOWN, OTHER])
    other_context = forms.CharField(
        label='Outro cenário (opcional)', required=False,
        widget=forms.Textarea(attrs={'class': 'textarea', 'rows': 3, 'spellcheck': 'true', 'placeholder': 'Descreva o que não apareceu nas opções.'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name != 'other_context':
                field.widget.attrs['class'] = 'select'

    def clean(self):
        cleaned = super().clean()
        for name in tuple(self.fields):
            if name == 'other_context':
                continue
            if cleaned.get(name) == 'other':
                cleaned[name] = 'unknown'
        return cleaned


class ProfilePreferencesForm(forms.Form):
    language = forms.ChoiceField(label='Linguagem', choices=[('simple', 'Direta e simples'), ('balanced', 'Equilibrada'), ('technical', 'Mais técnica')], required=False)
    detail = forms.ChoiceField(label='Nível de detalhe', choices=[('summary', 'Objetivo'), ('balanced', 'Intermediário'), ('detailed', 'Detalhado')], required=False)
    frequency = forms.ChoiceField(label='Frequência de acompanhamento', choices=[('weekly', 'Semanal'), ('biweekly', 'Quinzenal'), ('monthly', 'Mensal')], required=False)
    alerts = forms.ChoiceField(label='Como receber alertas', choices=[('immediate', 'Assim que forem identificados'), ('digest', 'Em um resumo periódico')], required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'select'


class ProfileLevelChoiceForm(forms.ModelForm):
    class Meta:
        model = BusinessProfileAssessment
        fields = ('selected_level', 'level_override_reason')
        labels = {'selected_level': 'Nível escolhido', 'level_override_reason': 'Por que este nível atende melhor agora?'}
        widgets = {
            'selected_level': forms.RadioSelect(attrs={'class': 'level-options'}),
            'level_override_reason': forms.Textarea(attrs={'rows': 2, 'class': 'textarea', 'spellcheck': 'true'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['selected_level'].choices = BusinessProfileAssessment.Level.choices

    def clean(self):
        cleaned = super().clean()
        selected = cleaned.get('selected_level')
        has_different_recommendation = (
            self.instance.recommended_level
            and selected
            and selected != self.instance.recommended_level
        )
        if has_different_recommendation and not (cleaned.get('level_override_reason') or '').strip():
            self.add_error('level_override_reason', 'Explique brevemente por que prefere um nível diferente.')
        return cleaned

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
                if isinstance(raw_value, str):
                    raw_value = re.sub(r'[^\d,.-]', '', raw_value)
                    if ',' in raw_value:
                        raw_value = raw_value.replace('.', '').replace(',', '.')
                    data[field_name] = raw_value
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
            'goal_type': forms.RadioSelect(attrs={'class': 'goal-type-input'}),
            'priority': forms.Select(attrs={'class': 'select'}),
            'notes': forms.Textarea(
                attrs={'class': 'textarea', 'rows': 3, 'placeholder': 'Detalhes adicionais...', 'spellcheck': 'true'}
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
