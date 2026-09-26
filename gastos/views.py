import calendar
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.db import transaction
from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .forms import (
    BusinessOnboardingForm,
    FinancialGoalForm,
    ImportUploadForm,
    LoginForm,
    MaturityProfileForm,
    ProfilePreferencesForm,
    SignupForm,
)
from .ia import gerar_resposta_financeira, groq_configured
from .import_service import confirm_batch, create_batch, remove_raw_file
from .models import (
    Business,
    BusinessProfileAssessment,
    FinancialGoal,
    FinancialTransaction,
    ImportBatch,
    ImportRow,
    ManagerialCategory,
)
from .profile_service import evaluate_maturity


EXPENSES = [
    {'name': 'Aluguel', 'category': 'Moradia', 'amount': 'R$ 1.800,00', 'initial': 'A'},
    {'name': 'Supermercado', 'category': 'Alimentação', 'amount': 'R$ 920,00', 'initial': 'S'},
    {'name': 'Netflix', 'category': 'Assinaturas', 'amount': 'R$ 55,00', 'initial': 'N'},
    {'name': 'Uber', 'category': 'Transporte', 'amount': 'R$ 280,00', 'initial': 'U'},
    {'name': 'Restaurante', 'category': 'Lazer', 'amount': 'R$ 420,00', 'initial': 'R'},
    {'name': 'Academia', 'category': 'Saúde', 'amount': 'R$ 120,00', 'initial': 'A'},
    {'name': 'Curso Online', 'category': 'Educação', 'amount': 'R$ 199,00', 'initial': 'C'},
    {'name': 'Cinema', 'category': 'Lazer', 'amount': 'R$ 85,00', 'initial': 'C'},
    {'name': 'Spotify', 'category': 'Assinaturas', 'amount': 'R$ 22,00', 'initial': 'S'},
    {'name': 'Farmácia', 'category': 'Saúde', 'amount': 'R$ 145,00', 'initial': 'F'},
]

CATEGORIES = [
    {'name': 'Moradia', 'amount': 'R$ 1.800', 'color': '#a855f7'},
    {'name': 'Alimentação', 'amount': 'R$ 920', 'color': '#c026d3'},
    {'name': 'Assinaturas', 'amount': 'R$ 77', 'color': '#7c3aed'},
    {'name': 'Transporte', 'amount': 'R$ 280', 'color': '#d946ef'},
    {'name': 'Lazer', 'amount': 'R$ 505', 'color': '#9333ea'},
    {'name': 'Saúde', 'amount': 'R$ 265', 'color': '#e879f9'},
    {'name': 'Educação', 'amount': 'R$ 199', 'color': '#8b5cf6'},
]

CATEGORY_COLORS = {
    item['name']: item['color']
    for item in CATEGORIES
}

SUMMARY_COLORS = ['#a855f7', '#c026d3', '#7c3aed', '#d946ef', '#e879f9', '#8b5cf6']


MONTH_NAMES = [
    'Janeiro',
    'Fevereiro',
    'Março',
    'Abril',
    'Maio',
    'Junho',
    'Julho',
    'Agosto',
    'Setembro',
    'Outubro',
    'Novembro',
    'Dezembro',
]


def current_month_label():
    today = timezone.localdate()
    return month_label(today)


def month_label(value):
    return f'{MONTH_NAMES[value.month - 1]} {value.year}'


def current_month_input():
    return month_input(timezone.localdate())


def month_input(value):
    return value.strftime('%Y-%m')


def current_date_input():
    return timezone.localdate().isoformat()


def current_month_date():
    today = timezone.localdate()
    return today.replace(day=1)


def month_from_input(value):
    if not value:
        return current_month_date()
    try:
        year, month = value.split('-', 1)
        return timezone.datetime(int(year), int(month), 1).date()
    except (TypeError, ValueError):
        return current_month_date()


def date_from_input(value):
    if not value:
        return timezone.localdate()
    try:
        year, month, day = value.split('-', 2)
        return timezone.datetime(int(year), int(month), int(day)).date()
    except (TypeError, ValueError):
        return timezone.localdate()


def monthly_url(reference_month):
    return f'{reverse("gastos:monthly")}?month={month_input(reference_month)}'


def monthly_all_url(reference_month):
    return f'{monthly_url(reference_month)}&view=all'


def current_business(user):
    display_name = user.get_full_name() or user.email or user.username
    business, _ = Business.objects.get_or_create(
        owner=user,
        is_default=True,
        defaults={'name': f'Negócio de {display_name}'},
    )
    return business


def category_for_name(business, name, group=ManagerialCategory.Group.UNCLASSIFIED):
    category_name = (name or 'Não classificadas').strip() or 'Não classificadas'
    category, _ = ManagerialCategory.objects.get_or_create(
        business=business,
        name=category_name,
        defaults={'group': group},
    )
    return category


def transactions_for_user(user):
    return FinancialTransaction.objects.filter(business__owner=user)


def realized_transactions_for_month(user, reference_month):
    return transactions_for_user(user).filter(
        status=FinancialTransaction.Status.REALIZED,
        date__year=reference_month.year,
        date__month=reference_month.month,
    )


def expense_months_with_records(user, limit=6):
    months = [
        value.replace(day=1)
        for value in transactions_for_user(user).filter(
            direction=FinancialTransaction.Direction.OUTFLOW,
            status=FinancialTransaction.Status.REALIZED,
        ).dates('date', 'month', order='ASC')
    ]
    if limit and len(months) > limit:
        return months[-limit:]
    return months


def date_for_month(reference_month, source_day):
    last_day = calendar.monthrange(reference_month.year, reference_month.month)[1]
    return reference_month.replace(day=min(source_day, last_day))


def ensure_fixed_expenses_for_month(user, reference_month):
    business = current_business(user)
    month_start = reference_month.replace(day=1)
    fixed_sources = transactions_for_user(user).filter(
        direction=FinancialTransaction.Direction.OUTFLOW,
        status=FinancialTransaction.Status.REALIZED,
        recurrence='fixed',
        date__lt=month_start,
    ).order_by('date')
    created = 0
    for source in fixed_sources:
        target_date = date_for_month(reference_month, source.date.day)
        exists = transactions_for_user(user).filter(
            business=business,
            direction=FinancialTransaction.Direction.OUTFLOW,
            recurrence='fixed',
            name=source.name,
            amount=source.amount,
            category=source.category,
            date=target_date,
        ).exists()
        if exists:
            continue
        FinancialTransaction.objects.create(
            business=business,
            created_by=user,
            direction=FinancialTransaction.Direction.OUTFLOW,
            name=source.name,
            amount=source.amount,
            date=target_date,
            category=source.category,
            status=FinancialTransaction.Status.REALIZED,
            certainty=source.certainty,
            recurrence='fixed',
            priority=source.priority,
            source=FinancialTransaction.Source.RECURRENCE,
            notes=source.notes,
        )
        created += 1
    return created


def money(value):
    return f'R$ {value:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')


def decimal_from_post(value, default='0'):
    raw = (value or default).strip()
    if ',' in raw:
        raw = raw.replace('.', '').replace(',', '.')
    try:
        return Decimal(raw)
    except (InvalidOperation, AttributeError):
        return Decimal(default)


def positive_amount_from_post(value):
    amount = decimal_from_post(value)
    return amount if amount > 0 else None


def percent(value, total):
    if not total:
        return 0
    return int((value / total) * 100)


def clamp(value, minimum=0, maximum=100):
    return max(minimum, min(maximum, value))


def summary_rows(items, total, label_key, color_map=None):
    rows = []
    for index, item in enumerate(items):
        amount = item['total'] or Decimal('0')
        item_percent = percent(amount, total)
        name = item[label_key]
        rows.append(
            {
                'name': name,
                'amount': money(amount),
                'percent': item_percent,
                'bar_width': clamp(item_percent),
                'color': (color_map or {}).get(name, SUMMARY_COLORS[index % len(SUMMARY_COLORS)]),
            }
        )
    return rows


def score_from_commitment(committed):
    if committed <= 50:
        return 90
    if committed <= 70:
        return 75
    if committed <= 90:
        return 55
    return 35


def score_label(score):
    if score >= 80:
        return 'Saudável'
    if score >= 60:
        return 'Atenção moderada'
    return 'Revisar gastos'


def dashboard_alert(committed, balance):
    if committed >= 90:
        return {
            'title': 'Atenção aos gastos',
            'message': 'Sua renda está quase toda comprometida neste mês. Revise despesas variáveis e prioridades.',
        }
    if balance > 0:
        return {
            'title': 'Bom sinal',
            'message': 'Você ainda tem saldo disponível neste mês. Continue acompanhando os lançamentos.',
        }
    return {
        'title': 'Comece registrando dados',
        'message': 'Cadastre sua renda mensal e suas despesas para liberar uma leitura mais fiel do dashboard.',
    }


def format_goal(goal, monthly_balance=None):
    required_monthly = goal.required_monthly_amount
    required_monthly_display = money(required_monthly) if required_monthly is not None else 'Sem prazo definido'
    balance_gap = None
    if required_monthly is not None and monthly_balance is not None:
        balance_gap = monthly_balance - required_monthly
    return {
        'id': goal.id,
        'name': goal.name,
        'type': goal.get_goal_type_display(),
        'priority': goal.get_priority_display(),
        'status': goal.get_status_display(),
        'target_amount': money(goal.target_amount),
        'saved_amount': money(goal.saved_amount),
        'remaining_amount': money(goal.remaining_amount),
        'progress_percent': goal.progress_percent,
        'target_date': goal.target_date,
        'months_remaining': goal.months_remaining,
        'required_monthly_amount': required_monthly_display,
        'balance_gap': money(balance_gap) if balance_gap is not None else None,
        'is_on_track': balance_gap is None or balance_gap >= 0,
        'notes': goal.notes,
    }


def goals_for_user(user, *, active_only=False):
    goals = FinancialGoal.objects.filter(user=user, business=current_business(user))
    if active_only:
        goals = goals.filter(status='active')
    return goals


def active_goals_for_user(user):
    return goals_for_user(user, active_only=True)


def goals_context_for_user(user, monthly_balance=None, *, active_only=True):
    queryset = goals_for_user(user, active_only=active_only)
    formatted_goals = [format_goal(goal, monthly_balance) for goal in queryset]
    featured_goal = formatted_goals[0] if formatted_goals else None
    return {
        'goals': formatted_goals,
        'featured_goal': featured_goal,
        'goals_count': len(formatted_goals),
    }


def ai_context_for_month(user, reference_month):
    business = current_business(user)
    assessment = completed_business_profile(user)
    business_goal = business.business_goal or 'Não informado'
    transactions = realized_transactions_for_month(user, reference_month)
    expenses = transactions.filter(direction=FinancialTransaction.Direction.OUTFLOW) # declara o mes de referencia
    total_expenses = expenses.aggregate(total=Sum('amount'))['total'] or Decimal('0') # calcula o total de despesas do mes de referencia
    income_amount = transactions.filter(direction=FinancialTransaction.Direction.INFLOW).aggregate(total=Sum('amount'))['total'] or Decimal('0') # calcula o total de renda do mes de referencia
    balance = income_amount - total_expenses # calcula o saldo do mes de referencia
    category_items = expenses.values('category__name').annotate(total=Sum('amount')).order_by('-total') # declara o total de despesas por categoria
    priority_labels = dict(FinancialTransaction.PRIORITY_CHOICES) # declara o total de despesas por prioridade
    priority_items = expenses.values('priority').annotate(total=Sum('amount')).order_by('-total') # declara o total de despesas por prioridade

    categories = ', '.join(
        f"{item['category__name']}: {money(item['total'] or Decimal('0'))}"
        for item in category_items
    ) or 'sem despesas por categoria'
    priorities = ', '.join(
        f"{priority_labels.get(item['priority'], item['priority'])}: {money(item['total'] or Decimal('0'))}"
        for item in priority_items
    ) or 'sem despesas por prioridade'
    active_goals = list(active_goals_for_user(user))
    goals = '; '.join(
        (
            f"{goal.name}: alvo {money(goal.target_amount)}, guardado {money(goal.saved_amount)}, "
            f"falta {money(goal.remaining_amount)}, progresso {goal.progress_percent}%, "
            f"necessario por mes {money(goal.required_monthly_amount) if goal.required_monthly_amount is not None else 'sem prazo definido'}"
        )
        for goal in active_goals
    ) or 'sem metas financeiras cadastradas'

    return '\n'.join(
        [
            'Contexto anonimizado de uma empresa.',
            f'Segmento: {business.segment or "Não informado"}',
            f'Atividade: {business.activity or "Não informada"}',
            f'Objetivo empresarial: {business_goal}',
            f'Nível gerencial calculado: {assessment.get_recommended_level_display() if assessment and assessment.recommended_level else "Inconclusivo"}',
            f'Mes de referencia: {month_label(reference_month)}',
            f'Renda cadastrada: {money(income_amount)}',
            f'Total de despesas: {money(total_expenses)}',
            f'Saldo: {money(balance)}',
            f'Percentual comprometido: {percent(total_expenses, income_amount)}%',
            f'Categorias: {categories}',
            f'Prioridades: {priorities}',
            f'Metas financeiras: {goals}',
        ]
    )


def session_user(request):
    if not request.user.is_authenticated:
        return None
    full_name = request.user.get_full_name() or default_user_from_email(request.user.email)
    return {
        'name': full_name,
        'email': request.user.email,
        'goal': request.user.profile.goal if hasattr(request.user, 'profile') else 'Controlar gastos',
        'initial': full_name[:1].upper() or 'U',
    }


def default_user_from_email(email):
    name_part = email.split('@', 1)[0].replace('.', ' ').replace('_', ' ').strip()
    return name_part.title() or 'Usuário'


def save_session_user(request, name, email, goal='Controlar gastos'):
    full_name = (name or '').strip() or default_user_from_email(email)
    email = (email or '').strip()
    return {
        'name': full_name,
        'email': email,
        'goal': (goal or '').strip() or 'Controlar gastos',
        'initial': full_name[:1].upper() or 'U',
    }


def completed_business_profile(user):
    if not user.is_authenticated:
        return None
    return BusinessProfileAssessment.objects.filter(
        business__owner=user,
        business__is_default=True,
        is_current=True,
        status=BusinessProfileAssessment.Status.COMPLETED,
    ).first()


def require_session_user(request):
    if not request.user.is_authenticated:
        return None, redirect('gastos:login')
    if completed_business_profile(request.user) is None:
        return None, redirect('gastos:onboarding_business')
    return session_user(request), None


def render_page(request, template_name, active_page=None, **context):
    business = current_business(request.user) if request.user.is_authenticated else None
    return render(
        request,
        template_name,
        {
            'active_page': active_page,
            'current_user': session_user(request),
            'current_business': business,
            'current_month': current_month_label(),
            'current_month_input': current_month_input(),
            'current_date_input': current_date_input(),
            **context,
        },
    )


def home(request):
    return render_page(request, 'gastos/home.html')


def landing(request):
    return render_page(request, 'gastos/landing.html')


def login(request):
    next_url = request.POST.get('next') or request.GET.get('next') or ''
    if request.user.is_authenticated:
        return redirect('gastos:dashboard' if completed_business_profile(request.user) else 'gastos:onboarding_business')
    form = LoginForm(request, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        auth_login(request, form.get_user())
        if completed_business_profile(form.get_user()) is None:
            return redirect('gastos:onboarding_business')
        if next_url and url_has_allowed_host_and_scheme(
            next_url,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            return redirect(next_url)
        return redirect('gastos:dashboard')
    return render_page(request, 'gastos/login.html', form=form, next=next_url)


def signup(request):
    if request.user.is_authenticated:
        return redirect('gastos:dashboard' if completed_business_profile(request.user) else 'gastos:onboarding_business')
    form = SignupForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            user = form.save()
        auth_login(request, user)
        return redirect('gastos:onboarding_business')
    return render_page(request, 'gastos/signup.html', form=form)


@require_POST
def logout(request):
    auth_logout(request)
    return redirect('gastos:landing')


def current_assessment(business):
    assessment, _ = BusinessProfileAssessment.objects.get_or_create(
        business=business,
        is_current=True,
        defaults={'questionnaire_version': '1.0'},
    )
    return assessment


def onboarding_business(request):
    if not request.user.is_authenticated:
        return redirect('gastos:login')
    business = current_business(request.user)
    form = BusinessOnboardingForm(request.POST or None, instance=business)
    if request.method == 'POST' and form.is_valid():
        business = form.save(commit=False)
        business.profile_updated_at = timezone.now()
        business.save()
        current_assessment(business)
        return redirect('gastos:onboarding_profile')
    return render_page(request, 'gastos/onboarding/business.html', form=form, onboarding_step=1)


def onboarding_profile(request):
    if not request.user.is_authenticated:
        return redirect('gastos:login')
    assessment = current_assessment(current_business(request.user))
    form = MaturityProfileForm(request.POST or None, initial=assessment.maturity_answers)
    if request.method == 'POST' and form.is_valid():
        result = evaluate_maturity(form.cleaned_data)
        assessment.maturity_answers = form.cleaned_data
        assessment.score = result['score']
        assessment.recommended_level = result['recommended_level']
        assessment.determining_factors = {
            'factors': result['determining_factors'],
            'missing_answers': result['missing_answers'],
            'inconsistencies': result['inconsistencies'],
            'minimum_score': result['calculated_score'],
            'maximum_score': result['maximum_possible_score'],
        }
        assessment.is_boundary = result['is_boundary']
        assessment.save()
        return redirect('gastos:onboarding_preferences')
    return render_page(request, 'gastos/onboarding/profile.html', form=form, onboarding_step=2)


def onboarding_preferences(request):
    if not request.user.is_authenticated:
        return redirect('gastos:login')
    assessment = current_assessment(current_business(request.user))
    if not assessment.maturity_answers:
        return redirect('gastos:onboarding_profile')
    form = ProfilePreferencesForm(request.POST or None, initial=assessment.preferences)
    if request.method == 'POST' and form.is_valid():
        assessment.preferences = form.cleaned_data
        assessment.status = BusinessProfileAssessment.Status.COMPLETED
        assessment.completed_at = timezone.now()
        assessment.save()
        return redirect('gastos:onboarding_result')
    return render_page(request, 'gastos/onboarding/preferences.html', form=form, onboarding_step=3)


def onboarding_result(request):
    if not request.user.is_authenticated:
        return redirect('gastos:login')
    assessment = current_assessment(current_business(request.user))
    if assessment.status != BusinessProfileAssessment.Status.COMPLETED:
        return redirect('gastos:onboarding_profile')
    levels = dict(BusinessProfileAssessment.Level.choices)
    factors = assessment.determining_factors or {}
    explanation = ''
    if request.method == 'POST':
        if not groq_configured():
            messages.error(request, 'A explicação assistida está temporariamente indisponível.')
        else:
            try:
                explanation = gerar_resposta_financeira(
                    'Explique em linguagem clara por que este nível foi recomendado, sem alterar o resultado e sem inferir dados ausentes.',
                    contexto=(
                        f'Nível calculado por regras: {levels.get(assessment.recommended_level, "inconclusivo")}.\n'
                        f'Pontuação: {assessment.score if assessment.score is not None else "não calculada"}.\n'
                        f'Fatores técnicos: {factors}.'
                    ),
                    purpose='analysis',
                    max_tokens=300,
                )
            except Exception:
                messages.error(request, 'A explicação assistida está temporariamente indisponível. O resultado determinístico permanece válido.')
    return render_page(
        request,
        'gastos/onboarding/result.html',
        assessment=assessment,
        level_label=levels.get(assessment.recommended_level, 'Resultado inconclusivo'),
        factors=factors,
        explanation=explanation,
        onboarding_step=4,
    )


@require_POST
def restart_profile_assessment(request):
    if not request.user.is_authenticated:
        return redirect('gastos:login')
    business = current_business(request.user)
    with transaction.atomic():
        BusinessProfileAssessment.objects.filter(business=business, is_current=True).update(is_current=False)
        BusinessProfileAssessment.objects.create(business=business, questionnaire_version='1.0')
    return redirect('gastos:onboarding_business')


def imports(request):
    user, response = require_session_user(request)
    if response:
        return response
    business = current_business(request.user)
    form = ImportUploadForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        try:
            batch = create_batch(
                business=business,
                user=request.user,
                uploaded_file=form.cleaned_data['file'],
                mapping={key: form.cleaned_data.get(key) for key in ('sheet_name', 'date_column', 'description_column', 'amount_column', 'direction_column')},
            )
        except Exception as exc:
            form.add_error('file', exc.messages[0] if hasattr(exc, 'messages') else 'Não foi possível processar o arquivo.')
        else:
            return redirect('gastos:import_review', public_id=batch.public_id)
    return render_page(request, 'gastos/imports/index.html', active_page='imports', user=user, form=form, batches=ImportBatch.objects.filter(business=business)[:12])


def import_review(request, public_id):
    user, response = require_session_user(request)
    if response:
        return response
    batch = get_object_or_404(ImportBatch, public_id=public_id, business__owner=request.user)
    categories = ManagerialCategory.objects.filter(business=batch.business, is_active=True)
    if request.method == 'POST' and batch.status == ImportBatch.Status.AWAITING_REVIEW:
        with transaction.atomic():
            for row in batch.rows.all():
                decision = request.POST.get(f'row_{row.id}_decision', row.decision)
                category_id = request.POST.get(f'row_{row.id}_category')
                if decision in dict(ImportRow.Decision.choices):
                    row.decision = decision
                row.confirmed_category = categories.filter(id=category_id).first() if category_id else None
                row.save(update_fields=['decision', 'confirmed_category', 'updated_at'])
        messages.success(request, 'Revisão salva. Nenhuma movimentação foi criada ainda.')
        return redirect('gastos:import_review', public_id=batch.public_id)
    return render_page(request, 'gastos/imports/review.html', active_page='imports', user=user, batch=batch, rows=batch.rows.select_related('suggested_category', 'confirmed_category'), categories=categories)


@require_POST
def import_confirm(request, public_id):
    user, response = require_session_user(request)
    if response:
        return response
    batch = get_object_or_404(ImportBatch, public_id=public_id, business__owner=request.user)
    created = confirm_batch(batch, request.user)
    messages.success(request, f'{created} movimentação(ões) criada(s).')
    return redirect('gastos:import_review', public_id=batch.public_id)


@require_POST
def import_cancel(request, public_id):
    user, response = require_session_user(request)
    if response:
        return response
    batch = get_object_or_404(ImportBatch, public_id=public_id, business__owner=request.user)
    if batch.status == ImportBatch.Status.AWAITING_REVIEW:
        remove_raw_file(batch)
        batch.status = ImportBatch.Status.CANCELLED
        batch.finalized_at = timezone.now()
        batch.save()
    return redirect('gastos:imports')


def dashboard(request):
    user, response = require_session_user(request)
    if response:
        return response
    reference_month = month_from_input(request.GET.get('month'))
    ensure_fixed_expenses_for_month(request.user, reference_month)
    transactions = realized_transactions_for_month(request.user, reference_month)
    expenses = transactions.filter(direction=FinancialTransaction.Direction.OUTFLOW)
    total_expenses = expenses.aggregate(total=Sum('amount'))['total'] or Decimal('0')
    income_amount = transactions.filter(direction=FinancialTransaction.Direction.INFLOW).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    balance = income_amount - total_expenses
    committed = percent(total_expenses, income_amount)
    score = score_from_commitment(committed)
    top_expenses = [
        {
            'name': expense.name,
            'category': expense.category,
            'amount': expense.amount_display,
            'initial': expense.name[:1].upper(),
        }
        for expense in expenses.order_by('-amount')[:5]
    ]
    category_items = list(expenses.values('category__name').annotate(total=Sum('amount')).order_by('-total'))
    category_summaries = summary_rows(category_items, total_expenses, 'category__name', CATEGORY_COLORS)
    priority_labels = dict(FinancialTransaction.PRIORITY_CHOICES)
    recurrence_labels = dict(FinancialTransaction.RECURRENCE_CHOICES)
    priority_items = [
        {
            'name': priority_labels.get(item['priority'], item['priority']),
            'total': item['total'] or Decimal('0'),
        }
        for item in expenses.values('priority').annotate(total=Sum('amount')).order_by('-total')
    ]
    recurrence_items = [
        {
            'name': recurrence_labels.get(item['recurrence'], item['recurrence']),
            'total': item['total'] or Decimal('0'),
        }
        for item in expenses.values('recurrence').annotate(total=Sum('amount')).order_by('-total')
    ]
    priority_summaries = summary_rows(priority_items, total_expenses, 'name')
    recurrence_summaries = summary_rows(recurrence_items, total_expenses, 'name')
    category_gradient = 'hsl(0 0% 100% / .08)'
    if category_summaries:
        offset = 0
        stops = []
        for category in category_summaries:
            next_offset = offset + category['percent']
            stops.append(f"{category['color']} {offset}% {max(next_offset, offset + 1)}%")
            offset = next_offset
        category_gradient = f"conic-gradient({', '.join(stops)})"
    history_months = expense_months_with_records(request.user)
    history_totals = []
    for item_month in history_months:
        ensure_fixed_expenses_for_month(request.user, item_month)
        month_transactions = realized_transactions_for_month(request.user, item_month)
        month_expenses = month_transactions.filter(direction=FinancialTransaction.Direction.OUTFLOW)
        month_total = month_expenses.aggregate(total=Sum('amount'))['total'] or Decimal('0')
        month_income_amount = month_transactions.filter(direction=FinancialTransaction.Direction.INFLOW).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        history_totals.append((item_month, month_total, month_income_amount))
    max_history_expense = max([item[1] for item in history_totals] + [Decimal('1')])
    monthly_history = [
        {
            'label': item_month.strftime('%m/%y'),
            'expenses_display': money(month_total),
            'income_display': money(month_income_amount),
            'balance_display': money(month_income_amount - month_total),
            'has_expenses': month_total > 0,
            'height': clamp(int((month_total / max_history_expense) * 100)) if month_total else 0,
        }
        for item_month, month_total, month_income_amount in history_totals
        if month_total > 0
    ]
    return render_page(
        request,
        'gastos/dashboard.html',
        active_page='dashboard',
        user=user,
        categories=CATEGORIES,
        category_summaries=category_summaries,
        priority_summaries=priority_summaries,
        recurrence_summaries=recurrence_summaries,
        top_expenses=top_expenses,
        income_amount_display=money(income_amount),
        total_expenses_display=money(total_expenses),
        balance_display=money(balance),
        current_month=month_label(reference_month),
        current_month_input=month_input(reference_month),
        committed=committed,
        committed_bar=clamp(committed),
        score=score,
        score_bar=score,
        score_label=score_label(score),
        category_gradient=category_gradient,
        monthly_history=monthly_history,
        alert=dashboard_alert(committed, balance),
        **goals_context_for_user(request.user, balance),
    )


def add_monthly_income(user, reference_month, amount, income_type):
    business = current_business(user)
    category = category_for_name(
        business,
        'Receitas não classificadas',
        ManagerialCategory.Group.REVENUE,
    )
    income_labels = {
        'fixed': 'Receita fixa',
        'variable': 'Receita variável',
    }
    return FinancialTransaction.objects.create(
        business=business,
        created_by=user,
        direction=FinancialTransaction.Direction.INFLOW,
        name=income_labels.get(income_type, 'Receita mensal'),
        amount=amount,
        date=reference_month,
        category=category,
        status=FinancialTransaction.Status.REALIZED,
        certainty=FinancialTransaction.Certainty.CONFIRMED,
        recurrence='variable',
        priority='essential',
        source=FinancialTransaction.Source.MANUAL,
    )


@require_POST
def ai_financial_insight(request):
    user, response = require_session_user(request)
    if response:
        return JsonResponse({'ok': False, 'message': 'Faça login para usar a IA.'}, status=401)
    if not groq_configured():
        return JsonResponse(
            {
                'ok': False,
                'message': 'Configure API_KEY ou GROQ_API_KEY no arquivo .env para ativar a IA.',
            },
            status=503,
        )

    reference_month = month_from_input(request.POST.get('month') or request.GET.get('month'))
    prompt = request.POST.get(
        'prompt',
        'Analise se os gastos e receitas do mes estao alinhados ao objetivo financeiro e as metas cadastradas do usuario. Responda em ate 5 topicos curtos, cada um iniciado por "-": situacao, meta, viabilidade, ponto de atencao e acao pratica.',
    )
    try:
        insight = gerar_resposta_financeira(
            prompt,
            ai_context_for_month(request.user, reference_month),
        )
    except Exception:
        return JsonResponse(
            {
                'ok': False,
                'message': 'Nao foi possivel consultar a IA agora. Tente novamente em instantes.',
            },
            status=502,
        )

    return JsonResponse({'ok': True, 'message': insight})


def goals(request):
    user, response = require_session_user(request)
    if response:
        return response
    form = FinancialGoalForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        goal = form.save(commit=False)
        goal.user = request.user
        goal.business = current_business(request.user)
        goal.save()
        messages.success(request, 'Meta financeira criada com sucesso.')
        return redirect('gastos:goals')

    reference_month = month_from_input(request.GET.get('month'))
    transactions = realized_transactions_for_month(request.user, reference_month)
    monthly_expenses = transactions.filter(direction=FinancialTransaction.Direction.OUTFLOW)
    total_expenses = monthly_expenses.aggregate(total=Sum('amount'))['total'] or Decimal('0')
    income_amount = transactions.filter(direction=FinancialTransaction.Direction.INFLOW).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    balance = income_amount - total_expenses
    goals_context = goals_context_for_user(request.user, balance, active_only=False)
    return render_page(
        request,
        'gastos/goals.html',
        active_page='goals',
        user=user,
        current_month=month_label(reference_month),
        current_month_input=month_input(reference_month),
        monthly_balance_display=money(balance),
        income_amount_display=money(income_amount),
        total_expenses_display=money(total_expenses),
        form=form,
        **goals_context,
    )


@require_POST
def delete_goal(request, goal_id):
    user, response = require_session_user(request)
    if response:
        return response
    goal = get_object_or_404(
        FinancialGoal,
        id=goal_id,
        user=request.user,
        business=current_business(request.user),
    )
    goal.delete()
    messages.success(request, 'Meta removida.')
    return redirect('gastos:goals')


def monthly(request):
    user, response = require_session_user(request)
    if response:
        return response
    if request.method == 'POST':
        reference_month = month_from_input(request.POST.get('reference_month'))
        amount = positive_amount_from_post(request.POST.get('income_amount'))
        if amount is None:
            messages.error(request, 'Informe um valor de receita maior que zero.')
            return redirect(monthly_url(reference_month))
        add_monthly_income(
            request.user,
            reference_month,
            amount,
            request.POST.get('income_type', 'fixed'),
        )
        return redirect(monthly_url(reference_month))

    reference_month = month_from_input(request.GET.get('month'))
    ensure_fixed_expenses_for_month(request.user, reference_month)
    transactions = realized_transactions_for_month(request.user, reference_month)
    income_entries = transactions.filter(direction=FinancialTransaction.Direction.INFLOW)
    monthly_expenses = transactions.filter(direction=FinancialTransaction.Direction.OUTFLOW)
    show_all_expenses = request.GET.get('view') == 'all'
    listed_expenses = (
        transactions_for_user(request.user).filter(direction=FinancialTransaction.Direction.OUTFLOW)
        if show_all_expenses
        else monthly_expenses
    )
    total_expenses = monthly_expenses.aggregate(total=Sum('amount'))['total'] or Decimal('0')
    all_expenses_count = transactions_for_user(request.user).filter(direction=FinancialTransaction.Direction.OUTFLOW).count()
    listed_expenses_count = listed_expenses.count()
    income_amount = income_entries.aggregate(total=Sum('amount'))['total'] or Decimal('0')
    balance = income_amount - total_expenses
    committed = int((total_expenses / income_amount) * 100) if income_amount else 0
    return render_page(
        request,
        'gastos/monthly.html',
        active_page='monthly',
        user=user,
        expenses=listed_expenses,
        income_entries=income_entries,
        income_count=income_entries.count(),
        income_amount=income_amount,
        income_amount_display=money(income_amount),
        current_month=month_label(reference_month),
        current_month_input=month_input(reference_month),
        show_all_expenses=show_all_expenses,
        all_expenses_count=all_expenses_count,
        listed_expenses_count=listed_expenses_count,
        monthly_expenses_url=monthly_url(reference_month),
        all_expenses_url=monthly_all_url(reference_month),
        total_expenses=total_expenses,
        total_expenses_display=money(total_expenses),
        balance=balance,
        balance_display=money(balance),
        committed=committed,
    )


@require_POST
def delete_monthly_income(request):
    user, response = require_session_user(request)
    if response:
        return response
    reference_month = month_from_input(request.POST.get('reference_month'))
    realized_transactions_for_month(request.user, reference_month).filter(
        direction=FinancialTransaction.Direction.INFLOW,
    ).delete()
    return redirect(monthly_url(reference_month))


def new_expense(request):
    user, response = require_session_user(request)
    if response:
        return response
    if request.method == 'POST':
        expense_date = date_from_input(request.POST.get('date'))
        amount = positive_amount_from_post(request.POST.get('amount'))
        if amount is None:
            messages.error(request, 'Informe um valor de despesa maior que zero.')
            return redirect(f'{reverse("gastos:new_expense")}?month={month_input(expense_date)}')
        business = current_business(request.user)
        FinancialTransaction.objects.create(
            business=business,
            created_by=request.user,
            direction=FinancialTransaction.Direction.OUTFLOW,
            name=request.POST.get('name', '').strip(),
            amount=amount,
            date=expense_date,
            category=category_for_name(business, request.POST.get('category', 'Outros')),
            status=FinancialTransaction.Status.REALIZED,
            certainty=FinancialTransaction.Certainty.CONFIRMED,
            recurrence=request.POST.get('recurrence', 'variable'),
            priority=request.POST.get('priority', 'essential'),
            source=FinancialTransaction.Source.MANUAL,
            notes=request.POST.get('notes', '').strip(),
        )
        return redirect(monthly_url(expense_date.replace(day=1)))
    reference_month = month_from_input(request.GET.get('month'))
    return render_page(
        request,
        'gastos/new-expense.html',
        active_page='new_expense',
        user=user,
        current_month=month_label(reference_month),
        current_month_input=month_input(reference_month),
        current_date_input=reference_month.isoformat(),
    )


def edit_expense(request, expense_id):
    user, response = require_session_user(request)
    if response:
        return response
    expense = get_object_or_404(
        FinancialTransaction,
        id=expense_id,
        business__owner=request.user,
        direction=FinancialTransaction.Direction.OUTFLOW,
    )
    if request.method == 'POST':
        expense_date = date_from_input(request.POST.get('date'))
        amount = positive_amount_from_post(request.POST.get('amount'))
        if amount is None:
            messages.error(request, 'Informe um valor de despesa maior que zero.')
            return redirect('gastos:edit_expense', expense_id=expense.id)
        expense.name = request.POST.get('name', '').strip()
        expense.amount = amount
        expense.date = expense_date
        expense.category = category_for_name(
            expense.business,
            request.POST.get('category', 'Outros'),
        )
        expense.recurrence = request.POST.get('recurrence', 'variable')
        expense.priority = request.POST.get('priority', 'essential')
        expense.notes = request.POST.get('notes', '').strip()
        expense.save()
        return redirect(monthly_url(expense_date.replace(day=1)))
    reference_month = expense.date.replace(day=1)
    return render_page(
        request,
        'gastos/new-expense.html',
        active_page='new_expense',
        user=user,
        edit_mode=True,
        expense=expense,
        form_action=reverse('gastos:edit_expense', args=[expense.id]),
        current_month=month_label(reference_month),
        current_month_input=month_input(reference_month),
        current_date_input=expense.date.isoformat(),
    )


@require_POST
def delete_expense(request, expense_id):
    user, response = require_session_user(request)
    if response:
        return response
    expense = get_object_or_404(
        FinancialTransaction,
        id=expense_id,
        business__owner=request.user,
        direction=FinancialTransaction.Direction.OUTFLOW,
    )
    reference_month = expense.date.replace(day=1)
    return_to_all = request.POST.get('return_to_all') == '1'
    expense.delete()
    if return_to_all:
        return redirect(monthly_all_url(reference_month))
    return redirect(monthly_url(reference_month))


def profile(request):
    user, response = require_session_user(request)
    if response:
        return response
    assessment = completed_business_profile(request.user)
    return render_page(
        request,
        'gastos/profile.html',
        active_page='profile',
        user=user,
        assessment=assessment,
        history=[
            {'month': current_month_label(), 'balance': 'R$ 0,00', 'score': 0},
        ],
    )
