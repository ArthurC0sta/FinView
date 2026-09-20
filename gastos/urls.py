from django.contrib.auth import views as auth_views
from django.urls import path
from django.urls import reverse_lazy

from . import views
from .forms import FinViewPasswordResetForm, FinViewSetPasswordForm

app_name = 'gastos'

urlpatterns = [
    path('', views.home, name='home'),
    path('landing/', views.landing, name='landing'),
    path('login/', views.login, name='login'),
    path(
        'password-reset/',
        auth_views.PasswordResetView.as_view(
            template_name='gastos/password_reset_form.html',
            email_template_name='gastos/password_reset_email.txt',
            subject_template_name='gastos/password_reset_subject.txt',
            form_class=FinViewPasswordResetForm,
            success_url=reverse_lazy('gastos:password_reset_done'),
        ),
        name='password_reset',
    ),
    path(
        'password-reset/done/',
        auth_views.PasswordResetDoneView.as_view(
            template_name='gastos/password_reset_done.html',
        ),
        name='password_reset_done',
    ),
    path(
        'reset/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            template_name='gastos/password_reset_confirm.html',
            form_class=FinViewSetPasswordForm,
            success_url=reverse_lazy('gastos:password_reset_complete'),
        ),
        name='password_reset_confirm',
    ),
    path(
        'reset/done/',
        auth_views.PasswordResetCompleteView.as_view(
            template_name='gastos/password_reset_complete.html',
        ),
        name='password_reset_complete',
    ),
    path('signup/', views.signup, name='signup'),
    path('logout/', views.logout, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('goals/', views.goals, name='goals'),
    path('goals/<int:goal_id>/delete/', views.delete_goal, name='delete_goal'),
    path('ai/insight/', views.ai_financial_insight, name='ai_financial_insight'),
    path('monthly/', views.monthly, name='monthly'),
    path('monthly/delete-income/', views.delete_monthly_income, name='delete_monthly_income'),
    path('new-expense/', views.new_expense, name='new_expense'),
    path('expenses/<int:expense_id>/edit/', views.edit_expense, name='edit_expense'),
    path('expenses/<int:expense_id>/delete/', views.delete_expense, name='delete_expense'),
    path('profile/', views.profile, name='profile'),
]
