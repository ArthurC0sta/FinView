import calendar
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.models import User
from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .ia import gerar_resposta_financeira, groq_configured
from .models import Expense, MonthlyIncome


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


def expense_months_with_records(user, limit=6):
    months = [
        value.replace(day=1)
        for value in Expense.objects.filter(user=user).dates('date', 'month', order='ASC')
    ]
    if limit and len(months) > limit:
        return months[-limit:]
    return months


def date_for_month(reference_month, source_day):
    last_day = calendar.monthrange(reference_month.year, reference_month.month)[1]
    return reference_month.replace(day=min(source_day, last_day))


def ensure_fixed_expenses_for_month(user, reference_month):
    month_start = reference_month.replace(day=1)
    fixed_sources = Expense.objects.filter(user=user, recurrence='fixed', date__lt=month_start).order_by('date')
    created = 0
    for source in fixed_sources:
        target_date = date_for_month(reference_month, source.date.day)
        exists = Expense.objects.filter(
            user=user,
            recurrence='fixed',
            name=source.name,
            amount=source.amount,
            category=source.category,
            date=target_date,
        ).exists()
        if exists:
            continue
        Expense.objects.create(
            user=user,
            name=source.name,
            amount=source.amount,
            date=target_date,
            category=source.category,
            recurrence='fixed',
            priority=source.priority,
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


def ai_context_for_month(user, reference_month):
    goal = user.profile.goal if hasattr(user, 'profile') else 'Controlar gastos'
    expenses = Expense.objects.filter(user=user, date__year=reference_month.year, date__month=reference_month.month)
    total_expenses = expenses.aggregate(total=Sum('amount'))['total'] or Decimal('0')
    income_amount = MonthlyIncome.objects.filter(user=user, reference_month=reference_month).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    balance = income_amount - total_expenses
    category_items = expenses.values('category').annotate(total=Sum('amount')).order_by('-total')
    priority_labels = dict(Expense.PRIORITY_CHOICES)
    priority_items = expenses.values('priority').annotate(total=Sum('amount')).order_by('-total')

    categories = ', '.join(
        f"{item['category']}: {money(item['total'] or Decimal('0'))}"
        for item in category_items
    ) or 'sem despesas por categoria'
    priorities = ', '.join(
        f"{priority_labels.get(item['priority'], item['priority'])}: {money(item['total'] or Decimal('0'))}"
        for item in priority_items
    ) or 'sem despesas por prioridade'

    return '\n'.join(
        [
            f'Usuario: {user.get_full_name() or default_user_from_email(user.email)}',
            f'Objetivo financeiro: {goal}',
            f'Mes de referencia: {month_label(reference_month)}',
            f'Renda cadastrada: {money(income_amount)}',
            f'Total de despesas: {money(total_expenses)}',
            f'Saldo: {money(balance)}',
            f'Percentual comprometido: {percent(total_expenses, income_amount)}%',
            f'Categorias: {categories}',
            f'Prioridades: {priorities}',
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


def require_session_user(request):
    if not request.user.is_authenticated:
        return None, redirect('gastos:login')
    return session_user(request), None


def render_page(request, template_name, active_page=None, **context):
    return render(
        request,
        template_name,
        {
            'active_page': active_page,
            'current_user': session_user(request),
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
    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '')
        user = authenticate(request, username=email, password=password)
        if user:
            auth_login(request, user)
            return redirect('gastos:dashboard')
        messages.error(request, 'E-mail ou senha inválidos.')
    return render_page(request, 'gastos/login.html')


def signup(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '')
        goal = request.POST.get('goal', '').strip() or 'Controlar gastos'
        if User.objects.filter(username=email).exists():
            messages.error(request, 'Já existe uma conta com esse e-mail.')
            return render_page(request, 'gastos/signup.html')
        first_name, _, last_name = name.partition(' ')
        user = User.objects.create_user(
            username=email,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
        )
        user.profile.goal = goal
        user.profile.save()
        auth_login(request, user)
        return redirect('gastos:monthly')
    return render_page(request, 'gastos/signup.html')


def logout(request):
    auth_logout(request)
    return redirect('gastos:landing')


def dashboard(request):
    user, response = require_session_user(request)
    if response:
        return response
    reference_month = month_from_input(request.GET.get('month'))
    ensure_fixed_expenses_for_month(request.user, reference_month)
    expenses = Expense.objects.filter(user=request.user, date__year=reference_month.year, date__month=reference_month.month)
    total_expenses = expenses.aggregate(total=Sum('amount'))['total'] or Decimal('0')
    income_amount = MonthlyIncome.objects.filter(user=request.user, reference_month=reference_month).aggregate(total=Sum('amount'))['total'] or Decimal('0')
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
    category_items = list(expenses.values('category').annotate(total=Sum('amount')).order_by('-total'))
    category_summaries = summary_rows(category_items, total_expenses, 'category', CATEGORY_COLORS)
    priority_labels = dict(Expense.PRIORITY_CHOICES)
    recurrence_labels = dict(Expense.RECURRENCE_CHOICES)
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
        month_expenses = Expense.objects.filter(user=request.user, date__year=item_month.year, date__month=item_month.month)
        month_total = month_expenses.aggregate(total=Sum('amount'))['total'] or Decimal('0')
        month_income_amount = MonthlyIncome.objects.filter(user=request.user, reference_month=item_month).aggregate(total=Sum('amount'))['total'] or Decimal('0')
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
        'Analise se os gastos do mes estao alinhados ao objetivo financeiro do usuario. Responda em ate 4 topicos curtos, cada um iniciado por "-": situacao, alinhamento, ponto de atencao e acao pratica.',
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


def monthly(request):
    user, response = require_session_user(request)
    if response:
        return response
    if request.method == 'POST':
        reference_month = month_from_input(request.POST.get('reference_month'))
        MonthlyIncome.objects.create(
            user=request.user,
            reference_month=reference_month,
            amount=decimal_from_post(request.POST.get('income_amount')),
            income_type=request.POST.get('income_type', 'fixed'),
        )
        return redirect(monthly_url(reference_month))

    reference_month = month_from_input(request.GET.get('month'))
    ensure_fixed_expenses_for_month(request.user, reference_month)
    income_entries = MonthlyIncome.objects.filter(user=request.user, reference_month=reference_month)
    monthly_expenses = Expense.objects.filter(user=request.user, date__year=reference_month.year, date__month=reference_month.month)
    show_all_expenses = request.GET.get('view') == 'all'
    listed_expenses = Expense.objects.filter(user=request.user) if show_all_expenses else monthly_expenses
    total_expenses = monthly_expenses.aggregate(total=Sum('amount'))['total'] or Decimal('0')
    all_expenses_count = Expense.objects.filter(user=request.user).count()
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
    MonthlyIncome.objects.filter(user=request.user, reference_month=reference_month).delete()
    return redirect(monthly_url(reference_month))


def new_expense(request):
    user, response = require_session_user(request)
    if response:
        return response
    if request.method == 'POST':
        expense_date = date_from_input(request.POST.get('date'))
        Expense.objects.create(
            user=request.user,
            name=request.POST.get('name', '').strip(),
            amount=decimal_from_post(request.POST.get('amount')),
            date=expense_date,
            category=request.POST.get('category', 'Outros'),
            recurrence=request.POST.get('recurrence', 'variable'),
            priority=request.POST.get('priority', 'essential'),
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
    expense = get_object_or_404(Expense, id=expense_id, user=request.user)
    if request.method == 'POST':
        expense_date = date_from_input(request.POST.get('date'))
        expense.name = request.POST.get('name', '').strip()
        expense.amount = decimal_from_post(request.POST.get('amount'))
        expense.date = expense_date
        expense.category = request.POST.get('category', 'Outros')
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
    expense = get_object_or_404(Expense, id=expense_id, user=request.user)
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
    return render_page(
        request,
        'gastos/profile.html',
        active_page='profile',
        user=user,
        history=[
            {'month': current_month_label(), 'balance': 'R$ 0,00', 'score': 0},
        ],
    )
