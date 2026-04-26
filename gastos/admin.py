from django.contrib import admin

from .models import Expense, MonthlyIncome, UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'goal')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'goal')


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'category', 'amount', 'date', 'recurrence', 'priority')
    list_filter = ('category', 'recurrence', 'priority', 'date')
    search_fields = ('name', 'user__email', 'category')


@admin.register(MonthlyIncome)
class MonthlyIncomeAdmin(admin.ModelAdmin):
    list_display = ('user', 'amount', 'income_type', 'reference_month')
    list_filter = ('income_type', 'reference_month')
    search_fields = ('user__email', 'user__first_name', 'user__last_name')
