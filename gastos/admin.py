from django.contrib import admin

from .models import (
    Business,
    BusinessProfileAssessment,
    Expense,
    FinancialGoal,
    FinancialTransaction,
    ManagerialCategory,
    ImportBatch,
    ImportRow,
    MonthlyIncome,
    UserProfile,
)


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


@admin.register(FinancialGoal)
class FinancialGoalAdmin(admin.ModelAdmin):
    list_display = ('name', 'business', 'user', 'target_amount', 'saved_amount', 'target_date', 'priority', 'status')
    list_filter = ('goal_type', 'priority', 'status', 'target_date')
    search_fields = ('name', 'user__email', 'notes')


@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'is_default', 'created_at')
    list_filter = ('is_default',)
    search_fields = ('name', 'owner__email')


@admin.register(ManagerialCategory)
class ManagerialCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'business', 'group', 'is_active', 'is_system')
    list_filter = ('group', 'is_active', 'is_system')
    search_fields = ('name', 'business__name', 'business__owner__email')


@admin.register(FinancialTransaction)
class FinancialTransactionAdmin(admin.ModelAdmin):
    list_display = ('name', 'business', 'direction', 'amount', 'date', 'category', 'status', 'source')
    list_filter = ('direction', 'status', 'certainty', 'recurrence', 'priority', 'source', 'date')
    search_fields = ('name', 'business__name', 'business__owner__email', 'category__name')


@admin.register(BusinessProfileAssessment)
class BusinessProfileAssessmentAdmin(admin.ModelAdmin):
    list_display = ('business', 'questionnaire_version', 'recommended_level', 'score', 'status', 'is_current', 'updated_at')
    list_filter = ('recommended_level', 'status', 'is_current')
    search_fields = ('business__name', 'business__owner__email')


class ImportRowInline(admin.TabularInline):
    model = ImportRow
    extra = 0
    readonly_fields = ('row_number', 'date', 'description', 'amount', 'direction', 'validation_status', 'possible_duplicate')


@admin.register(ImportBatch)
class ImportBatchAdmin(admin.ModelAdmin):
    list_display = ('original_name', 'business', 'file_format', 'status', 'total_rows', 'created_at')
    list_filter = ('file_format', 'status', 'created_at')
    search_fields = ('original_name', 'business__name', 'business__owner__email', 'file_hash')
    readonly_fields = ('public_id', 'file_hash', 'file_size', 'created_at', 'updated_at', 'finalized_at')
    inlines = (ImportRowInline,)
