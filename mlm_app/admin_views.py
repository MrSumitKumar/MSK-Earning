from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.db.models import Sum, Count, Q
from django.http import JsonResponse
from django.utils import timezone
from datetime import datetime, timedelta
from .models import *
from .views import website_details
import json
from django.contrib import messages


def is_admin(user):
    return user.is_superuser or user.is_staff

@login_required
@user_passes_test(is_admin)
def admin_dashboard(request):
    """Main admin dashboard with business analytics"""
    
    # Get date range for filtering
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    
    # Basic Statistics
    total_members = Member.objects.count()
    active_members = Member.objects.filter(status='Active').count()
    blocked_members = Member.objects.filter(block=True).count()
    
    # Registration Statistics
    new_members_today = Member.objects.filter(joined_on__date=today).count()
    new_members_week = Member.objects.filter(joined_on__date__gte=week_ago).count()
    new_members_month = Member.objects.filter(joined_on__date__gte=month_ago).count()
    
    # Financial Statistics
    company_wallet = CompanyWallet.objects.first()
    total_company_balance = company_wallet.balance if company_wallet else 0
    total_company_charges = company_wallet.charges_balance if company_wallet else 0
    
    # Member Financial Stats
    total_member_balance = Member.objects.aggregate(
        total=Sum('account_balance')
    )['total'] or 0
    
    total_member_income = Member.objects.aggregate(
        total=Sum('total_income')
    )['total'] or 0
    
    total_withdrawals = Member.objects.aggregate(
        total=Sum('total_withdrawal')
    )['total'] or 0
    
    # Payment Request Statistics
    pending_payments = PaymentRequest.objects.filter(status='Pending').count()
    approved_payments = PaymentRequest.objects.filter(status='Approved').count()
    completed_payments = PaymentRequest.objects.filter(status='Completed').count()
    rejected_payments = PaymentRequest.objects.filter(status='Rejected').count()
    
    pending_amount = PaymentRequest.objects.filter(
        status='Pending'
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    # Income Distribution
    income_stats = {
        'direct_income': Member.objects.aggregate(total=Sum('direct_income'))['total'] or 0,
        'level_income': Member.objects.aggregate(total=Sum('level_income'))['total'] or 0,
        'matching_income': Member.objects.aggregate(total=Sum('matching_income'))['total'] or 0,
        'resale_income': Member.objects.aggregate(total=Sum('resale_income'))['total'] or 0,
    }
    
    # Top Performers
    top_earners = Member.objects.filter(status='Active').order_by('-total_income')[:10]
    # Get top sponsors - simplified approach
    top_sponsors = Member.objects.filter(
        status='Active',
        total_income__gt=0
    ).order_by('-direct_income')[:10]
    
    # Recent Activities
    recent_registrations = Member.objects.select_related('user').order_by('-joined_on')[:10]
    recent_payments = PaymentRequest.objects.select_related('member__user').order_by('-request_date')[:10]
    recent_transactions = WalletTransaction.objects.select_related('user__user').order_by('-timestamp')[:10]
    
    # Binary Tree Statistics
    left_members = Member.objects.filter(position='Left').count()
    right_members = Member.objects.filter(position='Right').count()
    
    # Plans Statistics
    plan_stats = []
    for plan in Plan.objects.all():
        plan_members = MemberPlan.objects.filter(plan=plan, status='Active').count()
        plan_revenue = MemberPlan.objects.filter(
            plan=plan, status='Active'
        ).aggregate(total=Sum('plan__price'))['total'] or 0
        plan_stats.append({
            'plan': plan,
            'members': plan_members,
            'revenue': plan_revenue
        })
    
    context = {
        'site': website_details,
        'total_members': total_members,
        'active_members': active_members,
        'blocked_members': blocked_members,
        'new_members_today': new_members_today,
        'new_members_week': new_members_week,
        'new_members_month': new_members_month,
        'total_company_balance': total_company_balance,
        'total_company_charges': total_company_charges,
        'total_member_balance': total_member_balance,
        'total_member_income': total_member_income,
        'total_withdrawals': total_withdrawals,
        'pending_payments': pending_payments,
        'approved_payments': approved_payments,
        'completed_payments': completed_payments,
        'rejected_payments': rejected_payments,
        'pending_amount': pending_amount,
        'income_stats': income_stats,
        'top_earners': top_earners,
        'top_sponsors': top_sponsors,
        'recent_registrations': recent_registrations,
        'recent_payments': recent_payments,
        'recent_transactions': recent_transactions,
        'left_members': left_members,
        'right_members': right_members,
        'plan_stats': plan_stats,
    }
    
    return render(request, 'admin/admin_dashboard.html', context)

@login_required
@user_passes_test(is_admin)
def admin_members_management(request):
    """Members management page"""
    
    # Get filter parameters
    status_filter = request.GET.get('status', '')
    position_filter = request.GET.get('position', '')
    search_query = request.GET.get('search', '')
    
    # Base queryset
    members = Member.objects.select_related('user', 'sponsor').all()
    
    # Apply filters
    if status_filter:
        members = members.filter(status=status_filter)
    
    if position_filter:
        members = members.filter(position=position_filter)
    
    if search_query:
        members = members.filter(
            Q(user__username__icontains=search_query) |
            Q(user__first_name__icontains=search_query) |
            Q(user__email__icontains=search_query) |
            Q(mobile_no__icontains=search_query)
        )
    
    # Order by latest
    members = members.order_by('-joined_on')
    
    # Get statistics for this filtered set
    total_filtered = members.count()
    active_filtered = members.filter(status='Active').count()
    blocked_filtered = members.filter(block=True).count()
    
    context = {
        'site': website_details,
        'members': members[:100],  # Limit to 100 for performance
        'total_filtered': total_filtered,
        'active_filtered': active_filtered,
        'blocked_filtered': blocked_filtered,
        'status_filter': status_filter,
        'position_filter': position_filter,
        'search_query': search_query,
    }
    
    return render(request, 'admin/members_management.html', context)

@login_required
@user_passes_test(is_admin)
def admin_financial_overview(request):
    """Financial overview and analytics"""
    
    # Date range filtering
    date_range = request.GET.get('range', '30')  # Default 30 days
    
    if date_range == '7':
        start_date = timezone.now().date() - timedelta(days=7)
    elif date_range == '30':
        start_date = timezone.now().date() - timedelta(days=30)
    elif date_range == '90':
        start_date = timezone.now().date() - timedelta(days=90)
    else:
        start_date = timezone.now().date() - timedelta(days=365)
    
    # Financial Analytics
    company_wallet = CompanyWallet.objects.first()
    
    # Income breakdown
    income_data = {
        'direct': Member.objects.aggregate(total=Sum('direct_income'))['total'] or 0,
        'level': Member.objects.aggregate(total=Sum('level_income'))['total'] or 0,
        'matching': Member.objects.aggregate(total=Sum('matching_income'))['total'] or 0,
        'resale': Member.objects.aggregate(total=Sum('resale_income'))['total'] or 0,
    }
    
    # Payment requests analytics
    payment_requests = PaymentRequest.objects.filter(
        request_date__date__gte=start_date
    )
    
    payment_stats = {
        'pending': payment_requests.filter(status='Pending').aggregate(
            count=Count('id'), amount=Sum('amount')
        ),
        'approved': payment_requests.filter(status='Approved').aggregate(
            count=Count('id'), amount=Sum('amount')
        ),
        'completed': payment_requests.filter(status='Completed').aggregate(
            count=Count('id'), amount=Sum('amount')
        ),
        'rejected': payment_requests.filter(status='Rejected').aggregate(
            count=Count('id'), amount=Sum('amount')
        ),
    }
    
    # Daily income trend (last 30 days)
    daily_income = []
    for i in range(30):
        date = timezone.now().date() - timedelta(days=i)
        day_income = IncomeHistory.objects.filter(
            created_at__date=date
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        daily_income.append({
            'date': date.strftime('%Y-%m-%d'),
            'income': float(day_income)
        })
    
    daily_income.reverse()
    
    # Top earning members
    top_earners = Member.objects.filter(
        total_income__gt=0
    ).order_by('-total_income')[:20]
    
    context = {
        'site': website_details,
        'company_wallet': company_wallet,
        'income_data': income_data,
        'payment_stats': payment_stats,
        'daily_income': json.dumps(daily_income),
        'top_earners': top_earners,
        'date_range': date_range,
    }
    
    return render(request, 'admin/financial_overview.html', context)

@login_required
@user_passes_test(is_admin)
def admin_plan_management(request):
    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'create_or_update':
            plan_id = request.POST.get('plan_id')
            name = request.POST.get('name')
            price = request.POST.get('price')
            direct = request.POST.get('direct')
            matching = request.POST.get('matching')

            if plan_id:  # Update
                plan = get_object_or_404(Plan, id=plan_id)
                plan.name = name
                plan.price = price
                plan.direct = direct
                plan.matching = matching
                plan.save()
                messages.success(request, 'Plan updated successfully!')
            else:  # Create
                Plan.objects.create(
                    name=name,
                    price=price,
                    direct=direct,
                    matching=matching
                )
                messages.success(request, 'New plan created successfully!')

            return redirect('admin_plans')

        elif action == 'delete':
            plan_id = request.POST.get('plan_id')
            plan = get_object_or_404(Plan, id=plan_id)
            plan.delete()
            messages.success(request, 'Plan deleted successfully!')
            return redirect('admin_plans')

    plans = Plan.objects.all()
    return render(request, 'admin/plans_management.html', {"plans": plans})

@login_required
@user_passes_test(is_admin)
def admin_payment_management(request):
    """Payment requests management"""
    
    status_filter = request.GET.get('status', '')
    
    payment_requests = PaymentRequest.objects.select_related('member__user').all()
    
    if status_filter:
        payment_requests = payment_requests.filter(status=status_filter)
    
    payment_requests = payment_requests.order_by('-request_date')
    
    # Quick stats
    stats = {
        'pending': PaymentRequest.objects.filter(status='Pending').count(),
        'approved': PaymentRequest.objects.filter(status='Approved').count(),
        'completed': PaymentRequest.objects.filter(status='Completed').count(),
        'rejected': PaymentRequest.objects.filter(status='Rejected').count(),
    }
    
    context = {
        'site': website_details,
        'payment_requests': payment_requests[:100],
        'stats': stats,
        'status_filter': status_filter,
    }
    
    return render(request, 'admin/payment_management.html', context)

@login_required
@user_passes_test(is_admin)
def admin_genealogy_tree(request):
    """Admin genealogy tree view"""
    
    # Get root members (those without sponsors or top-level)
    root_members = Member.objects.filter(
        Q(sponsor__isnull=True) | Q(level=1)
    ).select_related('user')[:20]
    
    context = {
        'site': website_details,
        'root_members': root_members,
    }
    
    return render(request, 'admin/genealogy_tree.html', context)

@login_required
@user_passes_test(is_admin)
def toggle_member_status(request, member_id):
    """Toggle member active/inactive status"""
    if request.method == 'POST':
        member = get_object_or_404(Member, id=member_id)
        
        if member.status == 'Active':
            member.status = 'Inactive'
        else:
            member.status = 'Active'
        
        member.save()
        
        return JsonResponse({
            'success': True,
            'new_status': member.status,
            'message': f'Member status updated to {member.status}'
        })
    
    return JsonResponse({'success': False, 'message': 'Invalid request'})

@login_required
@user_passes_test(is_admin)
def toggle_member_block(request, member_id):
    """Toggle member block/unblock status"""
    if request.method == 'POST':
        member = get_object_or_404(Member, id=member_id)
        
        member.block = not member.block
        member.save()
        
        status = 'blocked' if member.block else 'unblocked'
        
        return JsonResponse({
            'success': True,
            'blocked': member.block,
            'message': f'Member {status} successfully'
        })
    
    return JsonResponse({'success': False, 'message': 'Invalid request'})