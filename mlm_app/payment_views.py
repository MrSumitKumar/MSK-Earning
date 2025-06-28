from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from .models import Member, PaymentRequest, MemberBankDetails
from decimal import Decimal


@login_required
def payment_request_form(request):
    """Display payment request form"""
    try:
        member = request.user.mlm_profile
    except:
        messages.error(request, "Please complete your profile first.")
        return redirect('dashboard')
    
    # Get member's bank details
    bank_details = member.bank_details.first()
    
    context = {
        'member': member,
        'bank_details': bank_details,
        'minimum_withdrawal': 100,  # Minimum withdrawal amount
        'withdrawal_charges': 0,    # No charges for now
    }
    
    return render(request, 'user/wallet/payment_request.html', context)


@login_required
@require_http_methods(["POST"])
def create_payment_request(request):
    """Create a new payment request"""
    try:
        member = request.user.mlm_profile
    except:
        messages.error(request, "Please complete your profile first.")
        return redirect('dashboard')
    
    # Get form data
    request_type = request.POST.get('request_type', 'withdrawal')
    amount = Decimal(request.POST.get('amount', '0'))
    description = request.POST.get('description', '')
    
    # Bank details
    bank_name = request.POST.get('bank_name', '')
    account_number = request.POST.get('account_number', '')
    ifsc_code = request.POST.get('ifsc_code', '')
    account_holder_name = request.POST.get('account_holder_name', '')
    upi_id = request.POST.get('upi_id', '')
    
    # Validation
    if amount < 100:
        messages.error(request, "Minimum withdrawal amount is ₹100.")
        return redirect('payment_request_form')
    
    if amount > member.wallet_balance:
        messages.error(request, "Insufficient wallet balance.")
        return redirect('payment_request_form')
    
    # Validate payment method details
    if request_type in ['withdrawal', 'bank_transfer']:
        if not all([bank_name, account_number, ifsc_code, account_holder_name]):
            messages.error(request, "Please fill all bank details for bank transfer.")
            return redirect('payment_request_form')
    elif request_type == 'upi_transfer':
        if not upi_id:
            messages.error(request, "Please provide UPI ID for UPI transfer.")
            return redirect('payment_request_form')
    
    # Check for pending requests
    pending_requests = PaymentRequest.objects.filter(
        member=member, 
        status='pending'
    ).count()
    
    if pending_requests >= 3:
        messages.error(request, "You already have 3 pending payment requests. Please wait for approval.")
        return redirect('payment_request_form')
    
    # Create payment request
    payment_request = PaymentRequest.objects.create(
        member=member,
        request_type=request_type,
        amount=amount,
        wallet_balance_before=member.wallet_balance,
        description=description,
        bank_name=bank_name,
        account_number=account_number,
        ifsc_code=ifsc_code,
        account_holder_name=account_holder_name,
        upi_id=upi_id
    )
    
    messages.success(request, f"Payment request for ₹{amount} has been submitted successfully. Request ID: {payment_request.id}")
    return redirect('payment_requests_history')


@login_required
def payment_requests_history(request):
    """Display user's payment request history"""
    try:
        member = request.user.mlm_profile
    except:
        messages.error(request, "Please complete your profile first.")
        return redirect('dashboard')
    
    # Get payment requests
    payment_requests = PaymentRequest.objects.filter(member=member).order_by('-request_date')
    
    # Pagination
    paginator = Paginator(payment_requests, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Summary statistics
    summary = {
        'total_requested': PaymentRequest.objects.filter(member=member).count(),
        'pending': PaymentRequest.objects.filter(member=member, status='pending').count(),
        'approved': PaymentRequest.objects.filter(member=member, status='approved').count(),
        'completed': PaymentRequest.objects.filter(member=member, status='completed').count(),
        'rejected': PaymentRequest.objects.filter(member=member, status='rejected').count(),
    }
    
    context = {
        'member': member,
        'payment_requests': page_obj,
        'summary': summary,
    }
    
    return render(request, 'user/wallet/payment_requests_history.html', context)


@login_required
def cancel_payment_request(request, request_id):
    """Cancel a pending payment request"""
    try:
        member = request.user.mlm_profile
    except:
        messages.error(request, "Please complete your profile first.")
        return redirect('dashboard')
    
    payment_request = get_object_or_404(PaymentRequest, id=request_id, member=member)
    
    if payment_request.status == 'pending':
        payment_request.status = 'cancelled'
        payment_request.save()
        messages.success(request, "Payment request cancelled successfully.")
    else:
        messages.error(request, "Only pending requests can be cancelled.")
    
    return redirect('payment_requests_history')


@login_required
def payment_request_detail(request, request_id):
    """Display payment request details"""
    try:
        member = request.user.mlm_profile
    except:
        messages.error(request, "Please complete your profile first.")
        return redirect('dashboard')
    
    payment_request = get_object_or_404(PaymentRequest, id=request_id, member=member)
    
    context = {
        'member': member,
        'payment_request': payment_request,
    }
    
    return render(request, 'user/wallet/payment_request_detail.html', context)


@login_required
def check_balance_availability(request):
    """AJAX endpoint to check if withdrawal amount is available"""
    try:
        member = request.user.mlm_profile
        amount = Decimal(request.GET.get('amount', '0'))
        
        response_data = {
            'available': amount <= member.account_balance,
            'account_balance': float(member.account_balance),
            'requested_amount': float(amount),
            'remaining_balance': float(member.account_balance - amount) if amount <= member.account_balance else 0
        }
        
        return JsonResponse(response_data)
    except:
        return JsonResponse({'error': 'Invalid request'}, status=400)