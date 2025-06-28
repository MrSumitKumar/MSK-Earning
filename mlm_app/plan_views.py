from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db import transaction
from django.utils import timezone
from .models import *
from .views import website_details
import json

@login_required
def plan_activation(request):
    """View available plans for activation"""
    try:
        member = request.user.mlm_profile
    except:
        messages.error(request, "Member profile not found.")
        return redirect('dashboard')
    
    plans = Plan.objects.all()
    current_plan = MemberPlan.objects.filter(member=member, status='Active').first()
    
    context = {
        'site': website_details,
        'member': member,
        'plans': plans,
        'current_plan': current_plan,
    }
    
    return render(request, 'user/plans/plan_activation.html', context)

@login_required
def activate_plan(request, plan_id):
    """Activate a specific plan for the member"""
    if request.method == 'POST':
        try:
            member = request.user.mlm_profile
            plan = get_object_or_404(Plan, id=plan_id)
            
            # Check if member already has an active plan
            existing_plan = MemberPlan.objects.filter(member=member, status='Active').first()
            if existing_plan:
                messages.error(request, "You already have an active plan. Please contact admin for upgrades.")
                return redirect('plan_activation')
            
            # Check if member has sufficient wallet balance
            if member.wallet_balance < plan.price:
                messages.error(request, f"Insufficient wallet balance. Required: ₹{plan.price}, Available: ₹{member.wallet_balance}")
                return redirect('plan_activation')
            
            with transaction.atomic():
                # Deduct plan cost from member wallet balance
                member.wallet_balance -= plan.price
                member.status = 'Active'  # Automatically activate member
                member.save()
                
                # Create member plan record
                member_plan = MemberPlan.objects.create(
                    member=member,
                    plan=plan,
                    status='Active',
                    purchased_date=timezone.now()
                )
                
                # Create wallet transaction
                WalletTransaction.objects.create(
                    user=member,
                    transaction_type='Plan Purchase',
                    amount=plan.price,
                    balance_after=member.account_balance,
                    description=f'Plan activated: {plan.name}'
                )
                
                # Add plan cost to company wallet
                company_wallet, _ = CompanyWallet.objects.get_or_create(id=1)
                company_wallet.add_to_wallet(plan.price)
                
                # Calculate and distribute income to upline
                distribute_plan_income(member, plan)
                
                messages.success(request, f"Plan '{plan.name}' activated successfully!")
                
        except Exception as e:
            messages.error(request, f"Error activating plan: {str(e)}")
    
    return redirect('plan_activation')

@login_required
def request_plan_upgrade(request):
    """Request plan upgrade/change"""
    if request.method == 'POST':
        try:
            member = request.user.mlm_profile
            new_plan_id = request.POST.get('new_plan_id')
            reason = request.POST.get('reason', '')
            
            new_plan = get_object_or_404(Plan, id=new_plan_id)
            current_plan = MemberPlan.objects.filter(member=member, status='Active').first()
            
            if not current_plan:
                messages.error(request, "You don't have an active plan to upgrade.")
                return redirect('plan_activation')
            
            # Create upgrade request (using description field for upgrade requests)
            upgrade_request = PaymentRequest.objects.create(
                member=member,
                request_type='Plan Upgrade',
                amount=new_plan.price - current_plan.plan.price if new_plan.price > current_plan.plan.price else 0,
                description=f'Upgrade from {current_plan.plan.name} to {new_plan.name}. Reason: {reason}',
                status='Pending'
            )
            
            messages.success(request, "Plan upgrade request submitted. Admin will review your request.")
            
        except Exception as e:
            messages.error(request, f"Error submitting upgrade request: {str(e)}")
    
    return redirect('plan_activation')

def distribute_plan_income(member, plan):
    """Distribute income to upline members when a plan is purchased"""
    try:
        # Direct Income to Sponsor
        if member.sponsor:
            sponsor_member = member.sponsor.mlm_profile if hasattr(member.sponsor, 'mlm_profile') else None
            if sponsor_member and sponsor_member.status == 'Active':
                direct_income = plan.direct
                sponsor_member.direct_income += direct_income
                sponsor_member.today_income += direct_income
                sponsor_member.total_income += direct_income
                sponsor_member.account_balance += direct_income
                sponsor_member.save()
                
                # Record income history
                IncomeHistory.objects.create(
                    member=sponsor_member,
                    income_type='Direct',
                    amount=direct_income,
                    description=f'Direct income from {member.user.username} plan purchase'
                )
                
                # Create wallet transaction
                WalletTransaction.objects.create(
                    user=sponsor_member,
                    transaction_type='Direct Income',
                    amount=direct_income,
                    balance_after=sponsor_member.account_balance,
                    description=f'Direct income from {member.user.username}'
                )
        
        # Level Income Distribution
        calculate_level_income(member, plan)
        
        # Matching Income (Binary)
        calculate_matching_income(member, plan)
        
    except Exception as e:
        print(f"Error distributing income: {e}")

def calculate_level_income(member, plan):
    """Calculate and distribute level income"""
    try:
        levels = Level.objects.filter(plan=plan).order_by('level')
        current_member = member
        
        for level_obj in levels:
            # Find the member at this level
            for i in range(level_obj.level):
                if current_member.sponsor:
                    current_member = current_member.sponsor.mlm_profile if hasattr(current_member.sponsor, 'mlm_profile') else None
                    if not current_member:
                        break
                else:
                    break
            
            if current_member and current_member.status == 'Active' and current_member != member:
                level_income = level_obj.distributed_amount
                current_member.level_income += level_income
                current_member.today_income += level_income
                current_member.total_income += level_income
                current_member.account_balance += level_income
                current_member.save()
                
                # Record income history
                IncomeHistory.objects.create(
                    member=current_member,
                    income_type='Level',
                    amount=level_income,
                    description=f'Level {level_obj.level} income from {member.user.username}'
                )
                
                # Create wallet transaction
                WalletTransaction.objects.create(
                    user=current_member,
                    transaction_type='Level Income',
                    amount=level_income,
                    balance_after=current_member.account_balance,
                    description=f'Level {level_obj.level} income from {member.user.username}'
                )
                
    except Exception as e:
        print(f"Error calculating level income: {e}")

def calculate_matching_income(member, plan):
    """Calculate and distribute matching income for binary structure"""
    try:
        current_member = member
        
        # Traverse up the binary tree
        while current_member.sponsor:
            sponsor = current_member.sponsor.mlm_profile if hasattr(current_member.sponsor, 'mlm_profile') else None
            if not sponsor or sponsor.status != 'Active':
                break
            
            # Check if sponsor has members on both left and right
            left_count = Member.objects.filter(sponsor=sponsor.user, position='Left', status='Active').count()
            right_count = Member.objects.filter(sponsor=sponsor.user, position='Right', status='Active').count()
            
            if left_count > 0 and right_count > 0:
                # Calculate matching income based on plan
                matching_income = plan.matching
                sponsor.matching_income += matching_income
                sponsor.today_income += matching_income
                sponsor.total_income += matching_income
                sponsor.account_balance += matching_income
                
                # Update matching pairs
                sponsor.matching_pairs += 1
                sponsor.save()
                
                # Record income history
                IncomeHistory.objects.create(
                    member=sponsor,
                    income_type='Matching',
                    amount=matching_income,
                    description=f'Matching income from {member.user.username} (L:{left_count}, R:{right_count})'
                )
                
                # Create wallet transaction
                WalletTransaction.objects.create(
                    user=sponsor,
                    transaction_type='Matching Income',
                    amount=matching_income,
                    balance_after=sponsor.account_balance,
                    description=f'Matching income from {member.user.username}'
                )
            
            current_member = sponsor
            
    except Exception as e:
        print(f"Error calculating matching income: {e}")

@login_required
def plan_history(request):
    """View member's plan history"""
    try:
        member = request.user.mlm_profile
        member_plans = MemberPlan.objects.filter(member=member).order_by('-purchased_date')
        
        context = {
            'site': website_details,
            'member': member,
            'member_plans': member_plans,
        }
        
        return render(request, 'user/plans/plan_history.html', context)
        
    except Exception as e:
        messages.error(request, f"Error loading plan history: {str(e)}")
        return redirect('dashboard')