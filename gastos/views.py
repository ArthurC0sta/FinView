from django.shortcuts import render


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


def render_page(request, template_name, active_page=None, **context):
    return render(request, template_name, {'active_page': active_page, **context})


def home(request):
    return render_page(request, 'gastos/home.html')


def landing(request):
    return render_page(request, 'gastos/landing.html')


def login(request):
    return render_page(request, 'gastos/login.html')


def signup(request):
    return render_page(request, 'gastos/signup.html')


def dashboard(request):
    return render_page(
        request,
        'gastos/dashboard.html',
        active_page='dashboard',
        categories=CATEGORIES,
        top_expenses=EXPENSES[:5],
    )


def monthly(request):
    return render_page(
        request,
        'gastos/monthly.html',
        active_page='monthly',
        expenses=EXPENSES,
    )


def new_expense(request):
    return render_page(request, 'gastos/new-expense.html', active_page='new_expense')


def profile(request):
    return render_page(
        request,
        'gastos/profile.html',
        active_page='profile',
        history=[
            {'month': 'Abril 2025', 'balance': 'R$ 2.954', 'score': 78},
            {'month': 'Março 2025', 'balance': 'R$ 2.500', 'score': 74},
            {'month': 'Fevereiro 2025', 'balance': 'R$ 2.100', 'score': 71},
            {'month': 'Janeiro 2025', 'balance': 'R$ 2.300', 'score': 70},
        ],
    )
