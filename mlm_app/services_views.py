from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .ewe_functions import recharge_mobile, create_order_id
from .models import Member, RechargeTransaction, CompanyWallet, WalletTransaction, IncomeHistory
from decimal import Decimal

@login_required
def initiate_recharge(request):
    """Handle mobile recharge requests."""
    if request.method == "POST":
        mobile_no = request.POST.get("mobile_no")
        amount_str = request.POST.get("amount")
        company_name = request.POST.get("company_name")
        is_stv = request.POST.get("is_stv", "false").lower() == "true"

        if not all([mobile_no, amount_str, company_name]):
            messages.error(request, "Please fill all required fields.")
            return redirect('mobile-recharge')

        try:
            amount = Decimal(amount_str)
            if amount <= 0:
                messages.error(request, "Amount must be greater than zero.")
                return redirect('mobile-recharge')
        except (ValueError, decimal.InvalidOperation):
            messages.error(request, "Invalid amount format.")
            return redirect('mobile-recharge')

        try:
            member = Member.objects.get(user=request.user)
        except Member.DoesNotExist:
            messages.error(request, "Member profile not found.")
            return redirect('mobile-recharge')

        if amount > member.wallet_balance:
            messages.error(request, "Insufficient wallet balance.")
            return redirect('mobile-recharge')

        # Generate unique order ID
        order_id = create_order_id(10)
        while RechargeTransaction.objects.filter(order_id=order_id).exists():
            order_id = create_order_id(10)

        # Process recharge
        response = recharge_mobile(mobile_no, amount, company_name, order_id, is_stv)

        # Create transaction record
        transaction = RechargeTransaction.objects.create(
            user=request.user,
            mobile_no=mobile_no,
            amount=amount,
            company_name=company_name,
            order_id=order_id,
            status=response.get("status", "failed"),
            response_data=response
        )

        if response.get("status") == 'success':
            # Deduct amount from wallet
            member.wallet_balance -= amount
            
            # Calculate and add resale income (2% of recharge amount)
            resale_commission = amount * Decimal('0.02')  # 2%
            member.resale_income += resale_commission
            member.total_income += resale_commission
            member.today_income += resale_commission
            member.wallet_balance += resale_commission
            
            member.save(update_fields=[
                'wallet_balance', 'resale_income', 'total_income', 'today_income'
            ])

            # Record wallet transactions
            WalletTransaction.objects.create(
                user=member,
                transaction_type='recharge',
                amount=-amount,
                balance_after=member.wallet_balance - resale_commission,
                description=f'Mobile recharge for {mobile_no}'
            )
            
            WalletTransaction.objects.create(
                user=member,
                transaction_type='credit',
                amount=resale_commission,
                balance_after=member.wallet_balance,
                description=f'Resale commission for recharge {order_id}'
            )

            # Record income history
            IncomeHistory.objects.create(
                member=member,
                income_type='resale_income',
                amount=resale_commission,
                description=f'Resale commission from mobile recharge {order_id}'
            )

            # Update company wallet
            try:
                company_wallet, _ = CompanyWallet.objects.get_or_create(id=1)
                profit_margin = amount * Decimal('0.02')  # Company keeps 2%
                company_wallet.balance += profit_margin
                company_wallet.save()
            except Exception as e:
                print(f"Error updating company wallet: {e}")

            messages.success(request, f"Recharge successful! You earned ₹{resale_commission} commission.")
        else:
            messages.error(request, f"Recharge failed: {response.get('error', 'Unknown error')}")

        context = {
            "response": response, 
            "transaction": transaction,
            "member": member
        }
        return render(request, "service/mobile_recharge/recharge_result.html", context)

    # GET request - show recharge form
    try:
        member = Member.objects.get(user=request.user)
        history = RechargeTransaction.objects.filter(user=request.user).order_by("-recharge_date")[:10]
        
        context = {
            "history": history,
            "member": member,
            "companies": [
                {"code": "jio", "name": "Jio"},
                {"code": "airtel", "name": "Airtel"},
                {"code": "vi", "name": "Vi (Vodafone Idea)"},
                {"code": "bsnl", "name": "BSNL"},
            ]
        }
        return render(request, "service/mobile_recharge/recharge_form.html", context)
    except Member.DoesNotExist:
        messages.error(request, "Member profile not found.")
        return redirect('dashboard')

@login_required
def dth_recharge(request):
    """DTH recharge service."""
    context = {
        'service_name': 'DTH Recharge',
        'description': 'Recharge your DTH connection and earn commission',
        'status': 'Coming Soon'
    }
    return render(request, 'service/dth_recharge.html', context)

@login_required
def bill_payments(request):
    """Bill payment service."""
    context = {
        'service_name': 'Bill Payments',
        'description': 'Pay your utility bills and earn commission',
        'status': 'Coming Soon'
    }
    return render(request, 'service/bill_payments.html', context)

@login_required
def electricity_bill(request):
    """Electricity bill payment."""
    context = {
        'service_name': 'Electricity Bill',
        'description': 'Pay electricity bills online',
        'status': 'Coming Soon'
    }
    return render(request, 'service/electricity_bill.html', context)

@login_required
def gas_bill(request):
    """Gas bill payment."""
    context = {
        'service_name': 'Gas Bill',
        'description': 'Pay gas bills online',
        'status': 'Coming Soon'
    }
    return render(request, 'service/gas_bill.html', context)

@login_required
def mobile_data_packs(request):
    """Mobile data pack service."""
    context = {
        'service_name': 'Mobile Data Packs',
        'description': 'Purchase data packs and earn commission',
        'status': 'Coming Soon'
    }
    return render(request, 'service/mobile_data_packs.html', context)

@login_required
def insurance(request):
    """Insurance service."""
    context = {
        'service_name': 'Insurance',
        'description': 'Pay insurance premiums online',
        'status': 'Coming Soon'
    }
    return render(request, 'service/insurance.html', context)

@login_required
def loan_payments(request):
    """Loan payment service."""
    context = {
        'service_name': 'Loan Payments',
        'description': 'Pay loan EMIs online',
        'status': 'Coming Soon'
    }
    return render(request, 'service/loan_payments.html', context)

@login_required
def fastag_recharge(request):
    """FASTag recharge service."""
    context = {
        'service_name': 'FASTag Recharge',
        'description': 'Recharge your FASTag wallet',
        'status': 'Coming Soon'
    }
    return render(request, 'service/fastag_recharge.html', context)
