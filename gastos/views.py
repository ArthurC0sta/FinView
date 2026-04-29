from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.models import User
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

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

MONTH_SHORT_NAMES = [
    'Jan',
    'Fev',
    'Mar',
    'Abr',
    'Mai',
    'Jun',
    'Jul',
    'Ago',
    'Set',
    'Out',
    'Nov',
    'Dez',
]

CHART_COLORS = [
    '#a855f7',
    '#c026d3',
    '#7c3aed',
    '#d946ef',
    '#9333ea',
    '#e879f9',
    '#8b5cf6',
    '#38bdf8',
]


def current_month_label():
    today = timezone.localdate()
    return f'{MONTH_NAMES[today.month - 1]} {today.year}'


def current_month_input():
    return timezone.localdate().strftime('%Y-%m')


def current_month_date():
    today = timezone.localdate()
    return today.replace(day=1)


def shift_month(reference_month, months):
    month_index = reference_month.month - 1 + months
    year = reference_month.year + month_index // 12
    month = month_index % 12 + 1
    return reference_month.replace(year=year, month=month, day=1)


def month_from_input(value):
    if not value:
        return current_month_date()
    try:
        year, month = value.split('-', 1)
        return timezone.datetime(int(year), int(month), 1).date()
    except (TypeError, ValueError):
        return current_month_date()


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


def percent(part, whole):
    if not whole:
        return 0
    return int(round((part / whole) * 100))


def clamp(value, minimum=0, maximum=100):
    return max(minimum, min(maximum, value))


def financial_score(income_amount, total_expenses, superfluous_total):
    if not income_amount:
        return 0
    committed = percent(total_expenses, income_amount)
    superfluous_share = percent(superfluous_total, total_expenses) if total_expenses else 0
    score = 100
    if committed > 70:
        score -= (committed - 70)
    if committed > 100:
        score -= 20
    score -= int(superfluous_share * 0.35)
    if not total_expenses:
        score = 45
    return clamp(score)


def score_label(score):
    if score >= 80:
        return 'Saudável'
    if score >= 60:
        return 'Atenção leve'
    if score >= 40:
        return 'Atenção'
    if score > 0:
        return 'Crítico'
    return 'Sem dados'


def summary_rows(items, total_expenses, label_key, color_offset=0):
    rows = []
    for index, item in enumerate(items):
        total = item['total'] or Decimal('0')
        row_percent = percent(total, total_expenses)
        rows.append(
            {
                'name': item[label_key],
                'amount': money(total),
                'percent': row_percent,
                'bar_width': clamp(row_percent),
                'color': CHART_COLORS[(index + color_offset) % len(CHART_COLORS)],
            }
        )
    return rows


def category_gradient(category_summaries):
    if not category_summaries:
        return 'hsl(0 0% 100% / .08)'
    segments = []
    cursor = 0
    for category in category_summaries:
        end = cursor + category['percent']
        segments.append(f"{category['color']} {cursor}% {end}%")
        cursor = end
    if cursor < 100:
        segments.append(f"hsl(0 0% 100% / .08) {cursor}% 100%")
    return f"conic-gradient({', '.join(segments)})"


def dashboard_alert(income_amount, total_expenses, balance, committed, category_summaries):
    if not income_amount:
        return {
            'title': 'Cadastre sua renda mensal',
            'message': 'Sem renda cadastrada, o painel ainda não consegue calcular saldo, score e risco financeiro.',
        }
    if not total_expenses:
        return {
            'title': 'Cadastre suas despesas',
            'message': 'Sua renda já está registrada. Adicione despesas para cruzar categorias, prioridade e recorrência.',
        }
    if balance < 0:
        return {
            'title': 'Saldo negativo no mês',
            'message': f'Seus gastos passaram da renda em {money(abs(balance))}. Revise gastos variáveis e supérfluos primeiro.',
        }
    if committed >= 80:
        return {
            'title': 'Comprometimento elevado',
            'message': f'{committed}% da renda já está comprometida. Seu saldo atual é {money(balance)}.',
        }
    if category_summaries and category_summaries[0]['percent'] >= 40:
        category = category_summaries[0]
        return {
            'title': 'Concentração de gastos',
            'message': f'{category["name"]} concentra {category["percent"]}% dos gastos do mês ({category["amount"]}).',
        }
    return {
        'title': 'Mês sob controle',
        'message': f'Você ainda tem {money(balance)} disponível. Continue acompanhando os lançamentos para manter o score saudável.',
    }


def ai_insights(user_goal, income_amount, total_expenses, balance, committed, score, category_summaries, priority_summaries):
    top_category = category_summaries[0] if category_summaries else None
    top_priority = priority_summaries[0] if priority_summaries else None
    insights = []
    if not income_amount:
        insights.append({'kind': 'alert-t', 'label': '⚠️ Alerta', 'text': 'Cadastre sua renda mensal para liberar análises de saldo e comprometimento.'})
    elif balance < 0:
        insights.append({'kind': 'alert-t', 'label': '⚠️ Alerta', 'text': f'Seu saldo está negativo em {money(abs(balance))}. Priorize cortes nas despesas variáveis.'})
    elif committed >= 80:
        insights.append({'kind': 'alert-t', 'label': '⚠️ Alerta', 'text': f'{committed}% da sua renda já foi comprometida neste mês.'})
    else:
        insights.append({'kind': 'positive', 'label': '✅ Bom sinal', 'text': f'Seu saldo atual é {money(balance)} e o score financeiro está em {score}/100.'})

    if top_category:
        insights.append({'kind': 'tip', 'label': '💡 Dica', 'text': f'A categoria {top_category["name"]} lidera seus gastos com {top_category["amount"]}. Revise esse grupo antes dos demais.'})
    elif income_amount:
        insights.append({'kind': 'tip', 'label': '💡 Dica', 'text': 'Comece cadastrando as despesas fixas para o painel separar o essencial do ajustável.'})

    insights.append({'kind': 'goal', 'label': '🎯 Objetivo', 'text': f'Seu objetivo é {user_goal.lower()}. Use o saldo e as prioridades para decidir os próximos cortes.'})

    if top_priority:
        insights.append({'kind': 'positive', 'label': '📌 Prioridade', 'text': f'A maior parte registrada está em {top_priority["name"].lower()}, somando {top_priority["amount"]}.'})
    return insights


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
    reference_month = current_month_date()
    expenses = Expense.objects.filter(user=request.user, date__year=reference_month.year, date__month=reference_month.month)
    income = MonthlyIncome.objects.filter(user=request.user, reference_month=reference_month).first()
    total_expenses = expenses.aggregate(total=Sum('amount'))['total'] or Decimal('0')
    income_amount = income.amount if income else Decimal('0')
    balance = income_amount - total_expenses
    committed = percent(total_expenses, income_amount)
    committed_bar = clamp(committed)
    superfluous_total = expenses.filter(priority='superfluous').aggregate(total=Sum('amount'))['total'] or Decimal('0')
    score = financial_score(income_amount, total_expenses, superfluous_total)
    score_bar = clamp(score)
    top_expenses = [
        {
            'name': expense.name,
            'category': expense.category,
            'amount': expense.amount_display,
            'initial': expense.name[:1].upper(),
        }
        for expense in expenses.order_by('-amount')[:5]
    ]
    category_summaries = summary_rows(
        expenses.values('category').annotate(total=Sum('amount')).order_by('-total'),
        total_expenses,
        'category',
    )
    priority_labels = dict(Expense.PRIORITY_CHOICES)
    recurrence_labels = dict(Expense.RECURRENCE_CHOICES)
    priority_summaries = [
        {
            **row,
            'name': priority_labels.get(row['name'], row['name']),
        }
        for row in summary_rows(
            expenses.values('priority').annotate(total=Sum('amount')).order_by('-total'),
            total_expenses,
            'priority',
            color_offset=2,
        )
    ]
    recurrence_summaries = [
        {
            **row,
            'name': recurrence_labels.get(row['name'], row['name']),
        }
        for row in summary_rows(
            expenses.values('recurrence').annotate(total=Sum('amount')).order_by('-total'),
            total_expenses,
            'recurrence',
            color_offset=4,
        )
    ]
    monthly_history = []
    history_totals = []
    for offset in range(-5, 1):
        month = shift_month(reference_month, offset)
        month_expenses = Expense.objects.filter(user=request.user, date__year=month.year, date__month=month.month).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        month_income = MonthlyIncome.objects.filter(user=request.user, reference_month=month).first()
        month_income_amount = month_income.amount if month_income else Decimal('0')
        month_balance = month_income_amount - month_expenses
        history_totals.append(month_expenses)
        monthly_history.append(
            {
                'label': MONTH_SHORT_NAMES[month.month - 1],
                'expenses': month_expenses,
                'expenses_display': money(month_expenses),
                'income_display': money(month_income_amount),
                'balance_display': money(month_balance),
            }
        )
    max_history_total = max(history_totals) if history_totals else Decimal('0')
    for item in monthly_history:
        item['height'] = 8 if not max_history_total else max(8, clamp(percent(item['expenses'], max_history_total)))

    alert = dashboard_alert(income_amount, total_expenses, balance, committed, category_summaries)
    insights = ai_insights(user['goal'], income_amount, total_expenses, balance, committed, score, category_summaries, priority_summaries)
    return render_page(
        request,
        'gastos/dashboard.html',
        active_page='dashboard',
        user=user,
        category_summaries=category_summaries,
        category_gradient=category_gradient(category_summaries),
        priority_summaries=priority_summaries,
        recurrence_summaries=recurrence_summaries,
        top_expenses=top_expenses,
        monthly_history=monthly_history,
        income_amount_display=money(income_amount),
        total_expenses_display=money(total_expenses),
        balance_display=money(balance),
        committed=committed,
        committed_bar=committed_bar,
        score=score,
        score_bar=score_bar,
        score_label=score_label(score),
        alert=alert,
        insights=insights,
    )


def monthly(request):
    user, response = require_session_user(request)
    if response:
        return response
    if request.method == 'POST':
        reference_month = month_from_input(request.POST.get('reference_month'))
        MonthlyIncome.objects.update_or_create(
            user=request.user,
            reference_month=reference_month,
            defaults={
                'amount': decimal_from_post(request.POST.get('income_amount')),
                'income_type': request.POST.get('income_type', 'fixed'),
            },
        )
        return redirect('gastos:monthly')

    reference_month = current_month_date()
    income = MonthlyIncome.objects.filter(user=request.user, reference_month=reference_month).first()
    expenses = Expense.objects.filter(user=request.user, date__year=reference_month.year, date__month=reference_month.month)
    total_expenses = expenses.aggregate(total=Sum('amount'))['total'] or Decimal('0')
    income_amount = income.amount if income else Decimal('0')
    balance = income_amount - total_expenses
    committed = int((total_expenses / income_amount) * 100) if income_amount else 0
    return render_page(
        request,
        'gastos/monthly.html',
        active_page='monthly',
        user=user,
        expenses=expenses,
        income=income,
        income_amount=income_amount,
        income_amount_display=money(income_amount),
        total_expenses=total_expenses,
        total_expenses_display=money(total_expenses),
        balance=balance,
        balance_display=money(balance),
        committed=clamp(committed),
    )


@require_POST
def delete_monthly_income(request):
    user, response = require_session_user(request)
    if response:
        return response
    reference_month = month_from_input(request.POST.get('reference_month'))
    deleted, _ = MonthlyIncome.objects.filter(user=request.user, reference_month=reference_month).delete()
    if deleted:
        messages.success(request, 'Entrada mensal excluída com sucesso.')
    else:
        messages.info(request, 'Nenhuma entrada mensal encontrada para excluir.')
    return redirect('gastos:monthly')


def new_expense(request):
    user, response = require_session_user(request)
    if response:
        return response
    if request.method == 'POST':
        Expense.objects.create(
            user=request.user,
            name=request.POST.get('name', '').strip(),
            amount=decimal_from_post(request.POST.get('amount')),
            date=request.POST.get('date') or timezone.localdate(),
            category=request.POST.get('category', 'Outros'),
            recurrence=request.POST.get('recurrence', 'variable'),
            priority=request.POST.get('priority', 'essential'),
            notes=request.POST.get('notes', '').strip(),
        )
        return redirect('gastos:monthly')
    return render_page(request, 'gastos/new-expense.html', active_page='new_expense', user=user)


@require_POST
def delete_expense(request, expense_id):
    user, response = require_session_user(request)
    if response:
        return response
    expense = get_object_or_404(Expense, id=expense_id, user=request.user)
    expense.delete()
    messages.success(request, 'Despesa excluída com sucesso.')
    return redirect('gastos:monthly')


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
