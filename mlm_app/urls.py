from django.urls import path
from . import user_views, views, services_views, payment_views, plan_views
from django.contrib.auth import views as auth_views

urlpatterns = [
    # Main pages
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('contact/', views.contact, name='contact'),
    path('services/', views.services, name='services'),

    # Dashboard URLs
    path('dashboard/', views.dashboard, name='dashboard'),
    path('dashboard/referral-links/', views.referral_links, name='referral_links'),


    # Authentication
    path('login/', user_views.login_user, name='login'),
    path('accounts/login/', user_views.accounts_login_user, name='accounts_login'),
    path('logout/', user_views.logout_user, name='logout'),
    path('referral/<str:sponsor_username>/<str:position>/', user_views.register_with_referral, name='register_with_referral'),
    
    # Password Reset
    path('password-reset/', auth_views.PasswordResetView.as_view(template_name='user/account/password_reset.html'), name='password_reset'),
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(template_name='user/account/password_reset_done.html'), name='password_reset_done'),
    path('password-reset-confirm/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name='user/account/password_reset_confirm.html'), name='password_reset_confirm'),
    path('password-reset-complete/', auth_views.PasswordResetCompleteView.as_view(template_name='user/account/password_reset_complete.html'), name='password_reset_complete'),

    # User Profile & Settings
    path('profile/', user_views.profile, name='profile'),
    path('setting/profile/', user_views.setting, name='setting'),
    path('setting/payment/', user_views.payment_setting, name='payment_setting'),
    
    # Team Management
    path('direct_team/<int:sponsor_id>/', user_views.direct_team_view, name='direct_team'),
    path('left_team/<int:sponsor_id>/', user_views.left_team_view, name='left_team'),
    path('right_team/<int:sponsor_id>/', user_views.right_team_view, name='right_team'),
    path('level_wise_team/<int:member_id>/', user_views.levelwise_team_view, name='level_wise_team'),
    
    # Income Reports
    path('income/direct/', user_views.direct_income_history, name='direct_income_history'),
    path('income/binary/', user_views.binary_team_income, name='binary_team_income'),
    path('income/level/', user_views.level_income_history, name='level_income_history'),
    path('income/resale/', user_views.resale_income_history, name='resale_income_history'),
    
    # Wallet Management
    path('wallet/', user_views.wallet, name='wallet'),
    path('wallet/account_to_wallet/', user_views.account_to_wallet, name='account_to_wallet'),
    path('wallet/send_to_friend/', user_views.send_to_friend, name='send_to_friend'),
    path('wallet/cash_to_wallet/', user_views.cash_to_wallet, name='cash_to_wallet'),
    path('wallet/withdrawal/', user_views.account_to_bank_account, name='account_to_bank_account'),
    
    # Payment Request Management
    path('wallet/payment-request/', payment_views.payment_request_form, name='payment_request_form'),
    path('wallet/payment-request/create/', payment_views.create_payment_request, name='create_payment_request'),
    path('wallet/payment-requests/', payment_views.payment_requests_history, name='payment_requests_history'),
    path('wallet/payment-request/<int:request_id>/', payment_views.payment_request_detail, name='payment_request_detail'),
    path('wallet/payment-request/<int:request_id>/cancel/', payment_views.cancel_payment_request, name='cancel_payment_request'),
    path('api/check-balance/', payment_views.check_balance_availability, name='check_balance_availability'),

    # Genealogy Tree
    path('genealogy-tree/<int:member_id>/', user_views.genealogy_tree_view, name='genealogy_tree'),
    path('genealogy-tree-data/<int:member_id>/', user_views.genealogy_tree_data, name='genealogy_tree_data'),

    # Plan Management
    path('plans/', plan_views.plan_activation, name='plan_activation'),
    path('plans/activate/<int:plan_id>/', plan_views.activate_plan, name='activate_plan'),
    path('plans/upgrade-request/', plan_views.request_plan_upgrade, name='request_plan_upgrade'),
    path('plans/history/', plan_views.plan_history, name='plan_history'),
    
    # Services
    path('recharge/mobile/', services_views.initiate_recharge, name='mobile-recharge'),
    path('dth_recharge/', services_views.dth_recharge, name='dth-recharge'),
    path('bill_payments/', services_views.bill_payments, name='bill-payments'),
    path('electricity_bill/', services_views.electricity_bill, name='electricity-bill'),
    path('gas_bill/', services_views.gas_bill, name='gas-bill'),
    path('mobile_data_packs/', services_views.mobile_data_packs, name='mobile-data-packs'),
    path('insurance/', services_views.insurance, name='insurance'),
    path('loan_payments/', services_views.loan_payments, name='loan-payments'),
    path('fastag_recharge/', services_views.fastag_recharge, name='fastag-recharge'),
]
