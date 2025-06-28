from django.contrib.auth.views import PasswordResetView, PasswordResetDoneView, PasswordResetConfirmView, PasswordResetCompleteView
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth import logout, authenticate, login
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from .ewe_functions import *
from .models import *
from .views import website_details
from django.db import transaction
from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
import logging
from django.utils import timezone
from django.http import JsonResponse

logger = logging.getLogger(__name__)

def register_with_referral(request, sponsor_username, position=None):
    """Register new user with referral link."""
    try:
        sponsor_user = get_object_or_404(User, username=sponsor_username)
    except:
        messages.error(request, "Invalid referral link.")
        return redirect('home')

    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        mobile_no = request.POST.get('mobile_no')
        password = request.POST.get('password')
        position = request.POST.get('position')

        if not all([name, email, mobile_no, password, position]):
            messages.error(request, "All fields are required!")
            return redirect('register_with_referral', sponsor_username=sponsor_username, position=position)

        if User.objects.filter(email=email).exists():
            messages.error(request, "This email is already registered.")
            return redirect('register_with_referral', sponsor_username=sponsor_username, position=position)

        if Member.objects.filter(mobile_no=mobile_no).exists():
            messages.error(request, "This mobile number is already registered.")
            return redirect('register_with_referral', sponsor_username=sponsor_username, position=position)

        if not password:
            password = generate_random_password(6)

        username = generate_username()

        try:
            with transaction.atomic():
                # Create user first
                user = User.objects.create_user(
                    username=username,
                    first_name=name,
                    email=email,
                    password=password
                )

                # Get sponsor member
                try:
                    sponsor_member = sponsor_user.mlm_profile
                except:
                    sponsor_member = Member.objects.create(user=sponsor_user)

                # Create new member manually (avoiding signal conflicts)
                new_member = Member.objects.create(
                    user=user,
                    sponsor=sponsor_user,
                    position=position,
                    mobile_no=mobile_no,
                )

            # Handle team structures outside the atomic block
            try:
                # Create team structures for new member
                from .signals import create_team_structures_for_member
                create_team_structures_for_member(new_member)

                # Add to Sponsor's Direct Team
                direct_team, _ = DirectTeam.objects.get_or_create(user=sponsor_member)
                direct_team.members.add(new_member)
                
                # Place the Member in Left/Right Team
                if position == 'Left':
                    left_team, _ = LeftTeam.objects.get_or_create(user=sponsor_member)
                    left_team.add_member(new_member)
                elif position == 'Right':
                    right_team, _ = RightTeam.objects.get_or_create(user=sponsor_member)
                    right_team.add_member(new_member)

                # Place Member in Binary Tree
                sponsor_member.place_member(new_member, position)
            except Exception as e:
                logger.error(f"Error in team placement: {e}")

            # Send email with login credentials
            try:
                send_registration_email(email, username, password, sponsor_username)
                messages.success(request, "Registration successful! Login credentials have been emailed.")
            except Exception as e:
                messages.warning(request, f"Registration successful, but email delivery failed: {e}")

            return redirect('login')

        except Exception as e:
            messages.error(request, f"An error occurred: {e}")
            return redirect('register_with_referral', sponsor_username=sponsor_username, position=position)

    # Render the registration form
    return render(request, 'auth/register.html', {
        'position': position,
        'sponsor': sponsor_user,
        'site': website_details
    })

def accounts_login_user(request):
    """Redirect to login page."""
    return redirect('login') 

def login_user(request):
    """User login view with multiple authentication methods."""
    if request.method == 'POST':
        username_or_email_or_mobile = request.POST.get('username')
        password = request.POST.get('password')

        if not username_or_email_or_mobile or not password:
            messages.error(request, "Please enter both username and password.")
            return render(request, 'auth/login.html', {'site': website_details})

        user = None
        try:
            # Try username first
            user = authenticate(request, username=username_or_email_or_mobile, password=password)
            
            # Try email if username failed
            if user is None:
                user_by_email = User.objects.filter(email=username_or_email_or_mobile).first()
                if user_by_email:
                    user = authenticate(request, username=user_by_email.username, password=password)

            # Try mobile number if email failed
            if user is None:
                member = Member.objects.filter(mobile_no=username_or_email_or_mobile).first()
                if member:
                    user = authenticate(request, username=member.user.username, password=password)

        except Exception as e:
            messages.error(request, f"An error occurred during login: {e}")
            return render(request, 'auth/login.html', {'site': website_details})

        if user is not None:
            login(request, user)
            messages.success(request, "Login successful!")

            # Redirect based on user type
            if user.is_superuser:
                return redirect('/admin-panel/') 
            else:
                return redirect('dashboard')
        else:
            messages.error(request, "Invalid credentials. Please try again.")
    
    return render(request, 'auth/login.html', {'site': website_details})

def logout_user(request):
    """User logout view."""
    logout(request)
    messages.success(request, "You have been logged out.")
    return redirect('login')

def password_reset(request):
    """Redirect to password reset."""
    return redirect('/accounts/password_reset')

@login_required
def profile(request):
    """User profile view."""
    try:
        member = request.user.mlm_profile
        context = {
            'member': member,
            'site': website_details
        }
        return render(request, "user/account/profile.html", context)
    except:
        messages.error(request, 'Profile not found.')
        return redirect('dashboard')

@login_required
def setting(request):
    """Profile settings view."""
    if request.method == "POST":
        profile_image = request.FILES.get('profile_image')
        
        try:
            user = request.user
            member_profile = user.mlm_profile
        except ObjectDoesNotExist:
            messages.error(request, 'MLM Profile does not exist for this user.')
            return redirect('setting')
        
        if profile_image:
            member_profile.profile_image = profile_image
            member_profile.save(update_fields=['profile_image'])
            messages.success(request, 'Profile image has been successfully updated.')
        else:
            messages.error(request, 'No profile image was uploaded.')

    try:
        member = request.user.mlm_profile
        context = {
            'member': member,
            'site': website_details
        }
        return render(request, "user/account/setting.html", context)
    except:
        messages.error(request, 'Profile not found.')
        return redirect('dashboard')

@login_required
def payment_setting(request):
    """Payment settings view."""
    user = request.user
    
    try:
        mlm_member = getattr(user, 'mlm_profile', None)
        if not mlm_member:
            messages.error(request, 'MLM Profile does not exist for this user.')
            return redirect('dashboard')

        member, created = MemberBankDetails.objects.get_or_create(member=mlm_member)
        
    except Exception as e:
        messages.error(request, f"An error occurred: {e}")
        return redirect('dashboard')

    if request.method == "POST":
        upi = request.POST.get('upi_id', '').strip()
        bank_name = request.POST.get('bank_name', '').strip()
        bank_account = request.POST.get('bank_account', '').strip()
        bank_ifsc = request.POST.get('bank_ifsc', '').strip()

        updated_fields = []

        if upi and upi != member.upi_id:
            member.upi_id = upi
            updated_fields.append('upi_id')

        if bank_account and bank_account != member.bank_account:
            member.bank_account = bank_account
            updated_fields.append('bank_account')

        if bank_name and bank_name != member.bank_name:
            member.bank_name = bank_name
            updated_fields.append('bank_name')

        if bank_ifsc and bank_ifsc != member.bank_ifsc:
            member.bank_ifsc = bank_ifsc
            updated_fields.append('bank_ifsc')

        if updated_fields:
            member.save(update_fields=updated_fields)
            messages.success(request, "Payment details updated successfully!")
        else:
            messages.info(request, "No changes were made.")

        return redirect('payment_setting')

    context = {
        "member": member,
        'site': website_details
    }
    return render(request, "user/account/payment_details.html", context)

def direct_team_view(request, sponsor_id):
    """Display the direct team members of a given user."""
    try:
        sponsor = Member.objects.get(id=sponsor_id)
        team = DirectTeam.objects.filter(user=sponsor).first()
    except Member.DoesNotExist:
        messages.error(request, 'Member not found.')
        return redirect('dashboard')
    
    context = {
        'sponsor': sponsor,
        'team': team,
        'site': website_details
    }
    return render(request, 'user/team/direct.html', context)

def left_team_view(request, sponsor_id):
    """Display left team members."""
    try:
        sponsor = Member.objects.get(id=sponsor_id)
        team = LeftTeam.objects.filter(user=sponsor).first()
    except Member.DoesNotExist:
        messages.error(request, 'Member not found.')
        return redirect('dashboard')
    
    context = {
        'sponsor': sponsor,
        'team': team,
        'site': website_details
    }
    return render(request, 'user/team/left.html', context)

def right_team_view(request, sponsor_id):
    """Display right team members."""
    try:
        sponsor = Member.objects.get(id=sponsor_id)
        team = RightTeam.objects.filter(user=sponsor).first()
    except Member.DoesNotExist:
        messages.error(request, 'Member not found.')
        return redirect('dashboard')
    
    context = {
        'sponsor': sponsor,
        'team': team,
        'site': website_details
    }
    return render(request, 'user/team/right.html', context)

def levelwise_team_view(request, member_id):
    """Display team structure: direct-to-direct team by levels."""
    try:
        member = Member.objects.get(id=member_id)
        direct_team = DirectTeam.objects.filter(user=member).first()

        if not direct_team:
            levelwise_team = {}
        else:
            levelwise_team = direct_team.get_level_wise_team()
    except Member.DoesNotExist:
        messages.error(request, 'Member not found.')
        return redirect('dashboard')

    context = {
        'member': member,
        'levelwise_team': levelwise_team,
        'site': website_details,
    }
    return render(request, 'user/team/level_wise.html', context)

@login_required
def direct_income_history(request):
    """Display the direct team income of the logged-in user."""
    user = request.user
    member = user.mlm_profile
    history = IncomeHistory.objects.filter(member=member, income_type='direct_income')
    
    context = {
        'history': history,
        'member': member,
        'site': website_details
    }
    return render(request, 'user/income/direct_income_history.html', context)

@login_required
def binary_team_income(request):
    """Display the binary team income of the logged-in user."""
    user = request.user
    member = user.mlm_profile
    history = IncomeHistory.objects.filter(member=member, income_type='matching_income')
    
    context = {
        'history': history,
        'member': member,
        'site': website_details
    }
    return render(request, 'user/income/binary_team_income.html', context)

@login_required
def level_income_history(request):
    """Display the level income of the logged-in user."""
    user = request.user
    member = user.mlm_profile
    history = IncomeHistory.objects.filter(member=member, income_type='level_income')
    
    context = {
        'history': history,
        'member': member,
        'site': website_details
    }
    return render(request, 'user/income/level_income_history.html', context)

@login_required
def resale_income_history(request):
    """Display the resale income of the logged-in user."""
    user = request.user
    member = user.mlm_profile
    history = IncomeHistory.objects.filter(member=member, income_type='resale_income')
    
    context = {
        'history': history,
        'member': member,
        'site': website_details
    }
    return render(request, 'user/income/resale_income_history.html', context)

@login_required
def wallet(request):
    """Wallet management view."""
    try:
        member = request.user.mlm_profile
        transactions = member.wallet_transactions.all()[:10]  # Recent 10 transactions
        
        context = {
            'member': member,
            'transactions': transactions,
            'site': website_details
        }
        return render(request, "user/wallet/wallet.html", context)
    except:
        messages.error(request, 'Wallet not found.')
        return redirect('dashboard')

@login_required
def account_to_wallet(request):
    """Transfer from account balance to wallet."""
    if request.method == "POST":
        amount_str = request.POST.get('amount')
        
        if not amount_str:
            messages.error(request, "Please enter the amount to transfer.")
            return redirect('wallet')
        
        try:
            amount = Decimal(amount_str)
            if amount <= 99:
                messages.error(request, "Amount must be greater than 99.")
                return redirect('wallet')
                
            member = request.user.mlm_profile
            
            if amount > member.account_balance:
                messages.error(request, "Insufficient account balance.")
                return redirect('wallet')
            
            # Transfer amount
            member.account_balance -= amount
            member.wallet_balance += amount
            member.save(update_fields=['account_balance', 'wallet_balance'])
            
            # Record transaction
            WalletTransaction.objects.create(
                user=member,
                transaction_type='credit',
                amount=amount,
                balance_after=member.wallet_balance,
                description='Transfer from account balance'
            )
            
            messages.success(request, f"₹{amount} transferred to wallet successfully.")
            
        except (ValueError, DecimalConversionError):
            messages.error(request, "Invalid amount format.")
        except Exception as e:
            messages.error(request, f"Transfer failed: {e}")
    
    return redirect('wallet')

@login_required
def send_to_friend(request):
    """Send money to another member."""
    if request.method == "POST":
        recipient_username = request.POST.get('recipient_username')
        amount_str = request.POST.get('amount')
        
        if not all([recipient_username, amount_str]):
            messages.error(request, "Please fill all required fields.")
            return redirect('wallet')
        
        try:
            amount = Decimal(amount_str)
            if amount <= 0:
                messages.error(request, "Amount must be greater than zero.")
                return redirect('wallet')
                
            sender = request.user.mlm_profile
            
            if amount > sender.wallet_balance:
                messages.error(request, "Insufficient wallet balance.")
                return redirect('wallet')
            
            # Find recipient
            try:
                recipient_user = User.objects.get(username=recipient_username)
                recipient = recipient_user.mlm_profile
            except User.DoesNotExist:
                messages.error(request, "Recipient not found.")
                return redirect('wallet')
            
            # Transfer amount
            sender.wallet_balance -= amount
            recipient.wallet_balance += amount
            
            sender.save(update_fields=['wallet_balance'])
            recipient.save(update_fields=['wallet_balance'])
            
            # Record transactions
            WalletTransaction.objects.create(
                user=sender,
                transaction_type='transfer_out',
                amount=amount,
                balance_after=sender.wallet_balance,
                description=f'Transfer to {recipient_username}'
            )
            
            WalletTransaction.objects.create(
                user=recipient,
                transaction_type='transfer_in',
                amount=amount,
                balance_after=recipient.wallet_balance,
                description=f'Transfer from {request.user.username}'
            )
            
            messages.success(request, f"₹{amount} sent to {recipient_username} successfully.")
            
        except (ValueError, DecimalConversionError):
            messages.error(request, "Invalid amount format.")
        except Exception as e:
            messages.error(request, f"Transfer failed: {e}")
    
    return redirect('wallet')

@login_required
def cash_to_wallet(request):
    """Add cash to wallet (admin feature)."""
    messages.info(request, "Cash to wallet feature is under development.")
    return redirect('wallet')

@login_required
def account_to_bank_account(request):
    """Withdraw to bank account."""
    if request.method == "POST":
        amount_str = request.POST.get('amount')
        
        if not amount_str:
            messages.error(request, "Please enter withdrawal amount.")
            return redirect('wallet')
        
        try:
            amount = Decimal(amount_str)
            if amount <= 0:
                messages.error(request, "Amount must be greater than zero.")
                return redirect('wallet')
                
            member = request.user.mlm_profile
            
            if amount > member.account_balance:
                messages.error(request, "Insufficient account balance.")
                return redirect('wallet')
            
            # Check if bank details exist
            if not hasattr(member, 'bank_details') or not member.bank_details.first():
                messages.error(request, "Please update your bank details first.")
                return redirect('payment_setting')
            
            # Process withdrawal (this would typically involve admin approval)
            member.account_balance -= amount
            member.total_withdrawal += amount
            member.save(update_fields=['account_balance', 'total_withdrawal'])
            
            # Record transaction
            WalletTransaction.objects.create(
                user=member,
                transaction_type='withdrawal',
                amount=amount,
                balance_after=member.account_balance,
                description='Withdrawal to bank account'
            )
            
            messages.success(request, f"Withdrawal request for ₹{amount} submitted successfully.")
            
        except (ValueError, DecimalConversionError):
            messages.error(request, "Invalid amount format.")
        except Exception as e:
            messages.error(request, f"Withdrawal failed: {e}")
    
    return redirect('wallet')

@login_required
def genealogy_tree_view(request, member_id):
    """Display genealogy tree view."""
    try:
        member = Member.objects.get(id=member_id)

        # Calculate left and right team member totals
        left_counts = member.count_team_members('left')
        right_counts = member.count_team_members('right')

        context = {
            'member': member,
            'site': website_details,
            'left_count': left_counts['total'],
            'right_count': right_counts['total'],
            'left_active': left_counts['active'],
            'right_active': right_counts['active'],
            'left_inactive': left_counts['inactive'],
            'right_inactive': right_counts['inactive'],
        }

        return render(request, 'user/genealogy_tree.html', context)

    except Member.DoesNotExist:
        messages.error(request, 'Member not found.')
        return redirect('dashboard')

@login_required
def genealogy_tree_data(request, member_id):
    """Return genealogy tree data as JSON."""
    try:
        member = Member.objects.get(id=member_id)
        
        def get_member_data(m):
            return {
                'id': m.id,
                'name': m.user.first_name,
                'username': m.user.username,
                'status': m.status,
                'position': m.position,
                'left': get_member_data(Member.objects.get(user=m.left)) if m.left else None,
                'right': get_member_data(Member.objects.get(user=m.right)) if m.right else None,
            }
        
        tree_data = get_member_data(member)
        return JsonResponse(tree_data)
        
    except Member.DoesNotExist:
        return JsonResponse({'error': 'Member not found'}, status=404)
