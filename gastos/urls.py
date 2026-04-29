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
    path('monthly/', views.monthly, name='monthly'),
    path('new-expense/', views.new_expense, name='new_expense'),
    path('profile/', views.profile, name='profile'),
]
