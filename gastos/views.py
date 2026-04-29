from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.models import User
from django.db.models import Sum
from django.shortcuts import redirect, render
from django.utils import timezone

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


def current_month_label():
    today = timezone.localdate()
    return f'{MONTH_NAMES[today.month - 1]} {today.year}'


def current_month_input():
    return timezone.localdate().strftime('%Y-%m')


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
    top_expenses = [
        {
            'name': expense.name,
            'category': expense.category,
            'amount': expense.amount_display,
            'initial': expense.name[:1].upper(),
        }
        for expense in expenses.order_by('-amount')[:5]
    ]
    category_summaries = [
        {
            'name': item['category'],
            'amount': money(item['total'] or Decimal('0')),
        }
        for item in expenses.values('category').annotate(total=Sum('amount')).order_by('-total')
    ]
    priority_labels = dict(Expense.PRIORITY_CHOICES)
    recurrence_labels = dict(Expense.RECURRENCE_CHOICES)
    priority_summaries = [
        {'name': priority_labels.get(item['priority'], item['priority']), 'amount': money(item['total'] or Decimal('0'))}
        for item in expenses.values('priority').annotate(total=Sum('amount')).order_by('-total')
    ]
    recurrence_summaries = [
        {'name': recurrence_labels.get(item['recurrence'], item['recurrence']), 'amount': money(item['total'] or Decimal('0'))}
        for item in expenses.values('recurrence').annotate(total=Sum('amount')).order_by('-total')
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
        committed=committed,
    )


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
