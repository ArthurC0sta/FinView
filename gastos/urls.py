from django.urls import path
from . import views

app_name = 'gastos'

urlpatterns = [
    path('', views.home, name='home'),
    path('landing/', views.landing, name='landing'),
    path('login/', views.login, name='login'),
    path('signup/', views.signup, name='signup'),
    path('logout/', views.logout, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('ai/insight/', views.ai_financial_insight, name='ai_financial_insight'),
    path('monthly/', views.monthly, name='monthly'),
    path('monthly/delete-income/', views.delete_monthly_income, name='delete_monthly_income'),
    path('new-expense/', views.new_expense, name='new_expense'),
    path('expenses/<int:expense_id>/edit/', views.edit_expense, name='edit_expense'),
    path('expenses/<int:expense_id>/delete/', views.delete_expense, name='delete_expense'),
    path('profile/', views.profile, name='profile'),
]
