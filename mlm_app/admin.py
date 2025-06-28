from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import *

class MemberInline(admin.StackedInline):
    model = Member
    fk_name = 'user'
    can_delete = False
    verbose_name_plural = 'MLM Profile'
    extra = 0
    readonly_fields = ('joined_on', 'last_updated')

class CustomUserAdmin(BaseUserAdmin):
    inlines = (MemberInline,)

# Re-register User with custom admin
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)

@admin.register(CompanyWallet)
class CompanyWalletAdmin(admin.ModelAdmin):
    list_display = ('id', 'balance', 'charges_balance')
    readonly_fields = ('id',)

@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'direct', 'matching')
    search_fields = ('name',)

@admin.register(Level)
class LevelAdmin(admin.ModelAdmin):
    list_display = ('plan', 'level', 'distributed_amount', 'resale_percentage')
    list_filter = ('plan', 'level')

@admin.register(RankAndRewards)
class RankAndRewardsAdmin(admin.ModelAdmin):
    list_display = ('rank_no', 'rank_name', 'pairs', 'royalty', 'amount')
    list_filter = ('rank_no',)
    ordering = ('rank_no',)

@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ('user', 'mobile_no', 'sponsor', 'position', 'status', 'level', 'account_balance', 'joined_on')
    list_filter = ('status', 'position', 'joined_on', 'block')
    search_fields = ('user__username', 'user__first_name', 'user__email', 'mobile_no')
    readonly_fields = ('joined_on', 'last_updated', 'all_matching_pairs')
    
    fieldsets = (
        ('User Information', {
            'fields': ('user', 'profile_image', 'mobile_no')
        }),
        ('MLM Structure', {
            'fields': ('sponsor', 'head_member', 'left', 'right', 'position', 'level')
        }),
        ('Financial Information', {
            'fields': (
                'account_balance', 'wallet_balance', 'today_income', 'total_income',
                'direct_income', 'level_income', 'resale_income', 'matching_income',
                'total_withdrawal'
            )
        }),
        ('Rank & Matching', {
            'fields': ('rank_no', 'matching_pairs', 'all_matching_pairs')
        }),
        ('Status', {
            'fields': ('status', 'block', 'joined_on', 'last_updated')
        }),
    )

@admin.register(MemberBankDetails)
class MemberBankDetailsAdmin(admin.ModelAdmin):
    list_display = ('member', 'bank_name', 'bank_account', 'upi_id')
    search_fields = ('member__user__username', 'bank_name', 'bank_account')

@admin.register(MemberPlan)
class MemberPlanAdmin(admin.ModelAdmin):
    list_display = ('member', 'plan', 'purchased_date', 'status')
    list_filter = ('status', 'purchased_date', 'plan')
    search_fields = ('member__user__username',)

@admin.register(DirectTeam)
class DirectTeamAdmin(admin.ModelAdmin):
    list_display = ('user', 'team_members')
    search_fields = ('user__user__username',)

@admin.register(LeftTeam)
class LeftTeamAdmin(admin.ModelAdmin):
    list_display = ('user', 'team_members')
    search_fields = ('user__user__username',)

@admin.register(RightTeam)
class RightTeamAdmin(admin.ModelAdmin):
    list_display = ('user', 'team_members')
    search_fields = ('user__user__username',)

@admin.register(IncomeHistory)
class IncomeHistoryAdmin(admin.ModelAdmin):
    list_display = ('member', 'income_type', 'amount', 'description', 'created_at')
    list_filter = ('income_type', 'created_at')
    search_fields = ('member__user__username', 'description')
    date_hierarchy = 'created_at'

@admin.register(RechargeTransaction)
class RechargeTransactionAdmin(admin.ModelAdmin):
    list_display = ('user', 'mobile_no', 'amount', 'company_name', 'status', 'recharge_date')
    list_filter = ('status', 'company_name', 'recharge_date')
    search_fields = ('user__username', 'mobile_no', 'order_id')
    date_hierarchy = 'recharge_date'
    readonly_fields = ('recharge_date',)

@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = ('user', 'transaction_type', 'amount', 'balance_after', 'timestamp')
    list_filter = ('transaction_type', 'timestamp')
    search_fields = ('user__user__username', 'description')
    date_hierarchy = 'timestamp'
    readonly_fields = ('timestamp',)


class PaymentRequestAdmin(admin.ModelAdmin):
    list_display = ('member', 'request_type', 'amount', 'status', 'request_date', 'approved_by')
    list_filter = ('status', 'request_type', 'request_date')
    search_fields = ('member__user__username', 'member__user__email', 'account_number', 'upi_id')
    date_hierarchy = 'request_date'
    readonly_fields = ('request_date', 'wallet_balance_before')
    
    fieldsets = (
        ('Request Information', {
            'fields': ('member', 'request_type', 'amount', 'wallet_balance_before', 'description')
        }),
        ('Payment Details', {
            'fields': ('bank_name', 'account_number', 'ifsc_code', 'account_holder_name', 'upi_id')
        }),
        ('Status & Approval', {
            'fields': ('status', 'approved_by', 'approval_date', 'admin_notes', 'rejection_reason')
        }),
        ('Transaction Details', {
            'fields': ('transaction_id', 'completed_date')
        }),
        ('Timestamps', {
            'fields': ('request_date',)
        }),
    )
    
    actions = ['approve_requests', 'reject_requests', 'complete_requests']
    
    def approve_requests(self, request, queryset):
        updated = 0
        for payment_request in queryset.filter(status='pending'):
            if payment_request.approve(request.user):
                updated += 1
        self.message_user(request, f'{updated} payment requests approved successfully.')
    approve_requests.short_description = "Approve selected payment requests"
    
    def reject_requests(self, request, queryset):
        updated = 0
        for payment_request in queryset.filter(status='pending'):
            if payment_request.reject(request.user, "Bulk rejection"):
                updated += 1
        self.message_user(request, f'{updated} payment requests rejected.')
    reject_requests.short_description = "Reject selected payment requests"
    
    def complete_requests(self, request, queryset):
        updated = 0
        for payment_request in queryset.filter(status='approved'):
            if payment_request.complete():
                updated += 1
        self.message_user(request, f'{updated} payment requests completed successfully.')
    complete_requests.short_description = "Complete selected payment requests"

# Register PaymentRequest admin
admin.site.register(PaymentRequest, PaymentRequestAdmin)
