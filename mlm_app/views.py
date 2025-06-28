from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth.hashers import make_password
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.core.exceptions import ObjectDoesNotExist
from .models import Member

website_details = {
    "name": ['MSK Earning', 'MSK', 'msk earning', 'MSK EARNING', 'mskearning'],
    "about": """MSK Earning is an innovative multi-level marketing (MLM) platform designed to help individuals achieve financial independence by providing a simple, reliable, and effective way to earn income. Whether you are looking for an additional source of income, a new career opportunity, or a chance to grow as an entrepreneur, MSK Earning offers you a gateway to success. 
    Our mission is to create a community-driven platform where every member has equal opportunities to succeed. By integrating advanced technology with a user-friendly interface, we ensure that our members can easily navigate their earning journey while focusing on what matters most—building a better future for themselves and their families.
    """,
    "company": "MSK Earning",
    "tagline": "Your Gateway to Financial Freedom",
    "domain": "mskearning.com"
}

def home(request):
    """Homepage view showing company information and features."""
    if request.user.is_authenticated:
        return redirect('dashboard')
    else:    
        context = {
            'site': website_details,
            'features': [
                {
                    'title': 'Binary Income',
                    'description': 'Earn from your left and right team matching',
                    'icon': 'users'
                },
                {
                    'title': 'Level Income',
                    'description': 'Get income from multiple levels of your downline',
                    'icon': 'trending-up'
                },
                {
                    'title': 'Direct Income',
                    'description': 'Immediate income from direct referrals',
                    'icon': 'user-plus'
                },
                {
                    'title': 'Service Income',
                    'description': 'Earn from mobile recharge and other services',
                    'icon': 'smartphone'
                }
            ]
        }
        return render(request, "main/index.html", context)

def about(request):
    """About page with company information."""
    return render(request, "main/about.html", {'site': website_details})

def contact(request):
    """Contact page."""
    return render(request, "main/contact.html", {'site': website_details})

def services(request):
    """Services page showing available services."""
    services_list = [
        {
            'name': 'Mobile Recharge',
            'description': 'Recharge any mobile number and earn commission',
            'url': 'mobile-recharge',
            'icon': 'smartphone'
        },
        {
            'name': 'DTH Recharge',
            'description': 'DTH and satellite TV recharge services',
            'url': 'dth-recharge',
            'icon': 'tv'
        },
        {
            'name': 'Bill Payments',
            'description': 'Pay electricity, gas and other utility bills',
            'url': 'bill-payments',
            'icon': 'file-text'
        },
        {
            'name': 'Insurance',
            'description': 'Insurance premium payments',
            'url': 'insurance',
            'icon': 'shield'
        }
    ]
    
    return render(request, "main/services.html", {
        'site': website_details,
        'services': services_list
    })

@login_required
def dashboard(request):
    """Main dashboard for logged-in users."""
    if request.user.is_superuser:
        return redirect('/admin-panel/')

    try:
        member = get_object_or_404(Member, user=request.user)
    except:
        messages.error(request, 'MLM Profile not found. Please contact administrator.')
        return redirect('login')

    # Get the team counts
    left_team_count = member.left_team.team_members if hasattr(member, 'left_team') else 0
    right_team_count = member.right_team.team_members if hasattr(member, 'right_team') else 0
    direct_team_count = member.direct_team.team_members if hasattr(member, 'direct_team') else 0
    
    # Calculate team member counts
    all_left_team_count = member.count_team_members('left')
    all_right_team_count = member.count_team_members('right')
    total_team_count = all_left_team_count['total'] + all_right_team_count['total']
    
    # Get recent income history
    recent_income = member.income_history.all()[:5]
    
    # Generate referral links
    base_url = request.build_absolute_uri('/')
    referral_links = {
        'left': f"{base_url}referral/{member.user.username}/Left/",
        'right': f"{base_url}referral/{member.user.username}/Right/"
    }

    context = {
        'member': member,
        'site': website_details,
        'left_team_count': left_team_count,
        'right_team_count': right_team_count,
        'direct_team_count': direct_team_count,
        'all_left_team_count': all_left_team_count,    
        'all_right_team_count': all_right_team_count,  
        'total_team_count': total_team_count,
        'recent_income': recent_income,
        'referral_links': referral_links,
        'income_summary': {
            'today': member.today_income,
            'total': member.total_income,
            'direct': member.direct_income,
            'level': member.level_income,
            'matching': member.matching_income,
            'resale': member.resale_income
        }
    }

    return render(request, 'user/dashboard.html', context)


# API views for AJAX calls
@login_required
def referral_links(request):
    """Generate referral links for left and right placement"""
    try:
        member = Member.objects.get(user=request.user)
        base_url = request.build_absolute_uri('/referral/')
        
        # Generate referral links
        left_link = f"{base_url}{request.user.username}/Left"
        right_link = f"{base_url}{request.user.username}/Right"
        
        context = {
            'member': member,
            'left_referral_link': left_link,
            'right_referral_link': right_link,
        }
        return render(request, 'dashboard/referral_links.html', context)
    except Member.DoesNotExist:
        messages.error(request, 'Member profile not found')
        return redirect('dashboard')