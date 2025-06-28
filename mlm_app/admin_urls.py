from django.urls import path
from . import admin_views

urlpatterns = [
    path('', admin_views.admin_dashboard, name='admin_dashboard'),
    path('plans/', admin_views.admin_plan_management, name='admin_plans'),
    path('members/', admin_views.admin_members_management, name='admin_members'),
    path('financial/', admin_views.admin_financial_overview, name='admin_financial'),
    path('payments/', admin_views.admin_payment_management, name='admin_payments'),
    path('genealogy/', admin_views.admin_genealogy_tree, name='admin_genealogy'),
    path('toggle-member-status/<int:member_id>/', admin_views.toggle_member_status, name='toggle_member_status'),
    path('toggle-member-block/<int:member_id>/', admin_views.toggle_member_block, name='toggle_member_block'),
]