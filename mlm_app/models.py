from django.db import models
from django.contrib.auth.models import User
from django.conf import settings
from django.utils import timezone
from decimal import Decimal
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.timezone import now
from django.utils import timezone
import logging
from django.db.models import F
import json

logger = logging.getLogger(__name__)

def update_matching_income(member_plan):
    """
    Update matching pairs, rank, and matching income for each head member up to the 'admin' user.
    Uses the last plan price of the head member to calculate income, considering only active members.
    """
    try:
        member = member_plan.member
        parent_member = member.head_member.mlm_profile if member.head_member else None

        if not parent_member:
            return

        while parent_member.user.username != "admin":
            all_left_team_count = parent_member.count_team_members('left')['active']
            all_right_team_count = parent_member.count_team_members('right')['active']

            current_matching_pairs = min(all_left_team_count, all_right_team_count)
            new_matching_pairs = current_matching_pairs - parent_member.all_matching_pairs

            if new_matching_pairs > 0:
                last_plan = parent_member.plans.last()
                if not last_plan:
                    break

                matching_income = Decimal(last_plan.plan.matching)

                parent_member.matching_income += matching_income
                parent_member.total_income += matching_income
                parent_member.today_income += matching_income
                parent_member.account_balance += matching_income
                parent_member.all_matching_pairs += new_matching_pairs
                parent_member.matching_pairs += new_matching_pairs

                IncomeHistory.objects.create(member=parent_member, income_type='matching_income', amount=matching_income)

                next_rank = RankAndRewards.objects.filter(
                    pairs__lte=parent_member.matching_pairs, rank_no__gt=parent_member.rank_no
                ).order_by('rank_no').first()

                if next_rank:
                    parent_member.rank_no = next_rank.rank_no
                    parent_member.matching_pairs = 0 

                parent_member.save(update_fields=[
                    'matching_income', 'total_income', 'today_income', 'account_balance',
                    'all_matching_pairs', 'matching_pairs', 'rank_no'
                ])

                # Deduct income from company wallet
                try:
                    company_wallet, _ = CompanyWallet.objects.get_or_create(id=1)
                    company_wallet.deduct_from_wallet(matching_income)
                except Exception as e:
                    logger.exception(f"Error deducting matching income from company wallet: {e}")

            # Move to the next head member
            parent_member = parent_member.head_member.mlm_profile if parent_member.head_member else None
            if not parent_member:
                break

    except Exception as e:
        logger.exception(f"Error updating matching income for member {member.user.username}: {e}")

class CompanyWallet(models.Model): 
    balance = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    charges_balance = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))

    def add_to_wallet(self, amount):
        """Add a specified amount to the wallet."""
        if amount < 0:
            raise ValueError("Amount to add cannot be negative.")
        self.balance += Decimal(amount)
        self.save()
        return self.balance

    def deduct_from_wallet(self, amount):
        """Deduct a specified amount from the wallet."""
        if amount < 0:
            raise ValueError("Amount to deduct cannot be negative.")
        if amount > self.balance:
            raise ValueError("Insufficient balance in the wallet.")
        self.balance -= Decimal(amount)
        self.save()
        return self.balance

    def __str__(self):
        return f"Company: {self.balance}"

    class Meta:
        verbose_name = "Company Wallet"
        verbose_name_plural = "Company Wallets"

class Plan(models.Model):
    name = models.CharField(max_length=50)
    price = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    direct = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    matching = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))

    def __str__(self):
        return f"{self.name} - ₹{self.price}"

class Level(models.Model):
    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name="levels", null=True)
    level = models.IntegerField(default=0)
    distributed_amount = models.FloatField(default=0)
    resale_percentage = models.FloatField(default=0)

    def __str__(self):
        return f"Plan: {self.plan} | Level {self.level} - ₹{self.distributed_amount} - {self.resale_percentage}%"

class RankAndRewards(models.Model):
    rank_no = models.IntegerField(default=0, verbose_name="Rank Number")
    rank_name = models.CharField(max_length=30, verbose_name="Rank Name")
    royalty = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="Royalty Amount")
    pairs = models.IntegerField(default=0, verbose_name="Pairs Required")
    amount = models.IntegerField(default=0, verbose_name="Reward Amount")
    reward_name = models.CharField(max_length=100, null=True, blank=True, verbose_name="Reward Name")

    def is_eligible(self, user_pairs):
        """Check if a user is eligible for this reward."""
        return user_pairs >= self.pairs

    def __str__(self):
        return f"Rank: {self.rank_no} - {self.rank_name} "

    class Meta:
        verbose_name = "Rank and Reward"
        verbose_name_plural = "Ranks and Rewards"

class Member(models.Model):
    POSITION_CHOICES = [
        ('Left', 'Left'),
        ('Right', 'Right'),
    ]
    BLOCK_CHOICES = [
        ('True', 'True'),
        ('False', 'False'),
    ]
    STATUS_CHOICES = [
        ('Active', 'Active'),
        ('Inactive', 'Inactive'),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='mlm_profile')
    profile_image = models.ImageField(upload_to='profile_images/', null=True, blank=True)
    mobile_no = models.CharField(max_length=10, unique=True)
    sponsor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='sponsored_users')
    head_member = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='head_users')
    left = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='left_users')
    right = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='right_users')

    position = models.CharField(max_length=10, choices=POSITION_CHOICES, null=True, blank=True)
    level = models.PositiveIntegerField(default=0)

    account_balance = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    today_income  = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00') )
    total_income  = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00') )
    direct_income = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00') )
    level_income  = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00') )
    resale_income = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00') )

    
    rank_no = models.PositiveIntegerField(default=0)
    matching_pairs = models.PositiveIntegerField(default=0)

    all_matching_pairs = models.PositiveIntegerField(default=0)
    matching_income  = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'), help_text="Income from matching bonus.")

    wallet_balance = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'), help_text="Wallet balance for the member.")
    total_withdrawal = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'), help_text="Total amount withdrawn.")

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="Inactive")
    block = models.CharField(max_length=10, choices=BLOCK_CHOICES, default="False")
    last_updated = models.DateTimeField(auto_now=True)
    joined_on = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} | {self.user.first_name} | {self.status}"

    class Meta:
        verbose_name = 'MLM Profile'
        verbose_name_plural = 'MLM Profiles'
        ordering = ['-joined_on']
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['mobile_no']),
            models.Index(fields=['position']),
            models.Index(fields=['status']),
        ]

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        
    def update_status(self):
        if self.status == 'Inactive':
            self.status = 'Active'
            self.save()

    def place_member(self, new_member, position):
        if position not in dict(self.POSITION_CHOICES):
            raise ValueError("Position must be 'Left' or 'Right'.")

        new_member.head_member = self.user

        if position == 'Left':
            if self.left is None:
                self.left = new_member.user
            else:
                left_member = Member.objects.get(user=self.left)
                left_member.place_member(new_member, position)
        elif position == 'Right':
            if self.right is None:
                self.right = new_member.user
            else:
                right_member = Member.objects.get(user=self.right)
                right_member.place_member(new_member, position)

        self.save()
        new_member.save()

    def count_team_members(self, direction):
        count = {
            'active': 0,
            'inactive': 0,
            'total': 0,
        }
        
        try:
            if direction == 'left' and self.left:
                left_member = Member.objects.get(user=self.left)
                
                left_counts = left_member.count_team_members('left')
                right_counts = left_member.count_team_members('right')
                
                count['active'] += (1 if left_member.status == 'Active' else 0) + left_counts['active'] + right_counts['active']
                count['inactive'] += (1 if left_member.status == 'Inactive' else 0) + left_counts['inactive'] + right_counts['inactive']
                count['total'] += 1 + left_counts['total'] + right_counts['total']

            elif direction == 'right' and self.right:
                right_member = Member.objects.get(user=self.right)

                left_counts = right_member.count_team_members('left')
                right_counts = right_member.count_team_members('right')
                
                # Update the counts for the current right subtree
                count['active'] += (1 if right_member.status == 'Active' else 0) + left_counts['active'] + right_counts['active']
                count['inactive'] += (1 if right_member.status == 'Inactive' else 0) + left_counts['inactive'] + right_counts['inactive']
                count['total'] += 1 + left_counts['total'] + right_counts['total']

        except Member.DoesNotExist:
            pass

        return count

    def update_rank(self):
        """Automatically update rank based on matching pairs and reset matching_pairs."""
        next_rank = RankAndRewards.objects.filter(pairs__lte=self.matching_pairs, rank_no__gt=self.rank_no).order_by('rank_no').first()

        if next_rank:
            self.rank_no = next_rank.rank_no
            self.matching_pairs = 0
            self.save()

class MemberBankDetails(models.Model):
    member = models.ForeignKey('Member', on_delete=models.CASCADE, related_name='bank_details')
    upi_id = models.CharField(max_length=100, null=True, blank=True)
    bank_name = models.CharField(max_length=100, null=True, blank=True)
    bank_account = models.CharField(max_length=20, null=True, blank=True)
    bank_ifsc = models.CharField(max_length=15, null=True, blank=True)

    def __str__(self):
        return f"{self.member.user.username} - Bank Details"

    class Meta:
        verbose_name = "Member Bank Detail"
        verbose_name_plural = "Member Bank Details"

class MemberPlan(models.Model):
    PURCHASE_STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Completed', 'Completed'),
        ('Failed', 'Failed'),
    ]

    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name='plans')
    plan = models.ForeignKey(Plan, on_delete=models.CASCADE)
    purchased_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=PURCHASE_STATUS_CHOICES, default='Pending')

    def __str__(self):
        return f"{self.member.user.username} - {self.plan.name}"

    class Meta:
        verbose_name = "Member Plan"
        verbose_name_plural = "Member Plans"

class DirectTeam(models.Model):
    user = models.OneToOneField(Member, on_delete=models.CASCADE, related_name='direct_team')
    members = models.ManyToManyField(Member, related_name='direct_team_members', blank=True)

    @property
    def team_members(self):
        return self.members.count()

    def get_level_wise_team(self, max_level=10):
        """Get team members organized by levels (direct to direct)."""
        level_wise_team = {}
        
        # Level 1: Direct members
        level_1_members = list(self.members.all())
        if level_1_members:
            level_wise_team[1] = level_1_members
        
        # Get subsequent levels
        for level in range(2, max_level + 1):
            level_members = []
            previous_level = level_wise_team.get(level - 1, [])
            
            for member in previous_level:
                if hasattr(member, 'direct_team'):
                    level_members.extend(member.direct_team.members.all())
            
            if level_members:
                level_wise_team[level] = level_members
            else:
                break
        
        return level_wise_team

    def __str__(self):
        return f"{self.user.user.username} - Direct Team ({self.team_members})"

    class Meta:
        verbose_name = "Direct Team"
        verbose_name_plural = "Direct Teams"

class LeftTeam(models.Model):
    user = models.OneToOneField(Member, on_delete=models.CASCADE, related_name='left_team')
    members = models.ManyToManyField(Member, related_name='left_team_members', blank=True)

    @property
    def team_members(self):
        return self.members.count()

    def add_member(self, member):
        """Add a member to the left team and all uplines."""
        self.members.add(member)
        
        # Add to all uplines left teams
        current_head = self.user.head_member
        while current_head:
            try:
                head_member = Member.objects.get(user=current_head)
                left_team, _ = LeftTeam.objects.get_or_create(user=head_member)
                left_team.members.add(member)
                current_head = head_member.head_member
            except Member.DoesNotExist:
                break

    def __str__(self):
        return f"{self.user.user.username} - Left Team ({self.team_members})"

    class Meta:
        verbose_name = "Left Team"
        verbose_name_plural = "Left Teams"

class RightTeam(models.Model):
    user = models.OneToOneField(Member, on_delete=models.CASCADE, related_name='right_team')
    members = models.ManyToManyField(Member, related_name='right_team_members', blank=True)

    @property
    def team_members(self):
        return self.members.count()

    def add_member(self, member):
        """Add a member to the right team and all uplines."""
        self.members.add(member)
        
        # Add to all uplines right teams
        current_head = self.user.head_member
        while current_head:
            try:
                head_member = Member.objects.get(user=current_head)
                right_team, _ = RightTeam.objects.get_or_create(user=head_member)
                right_team.members.add(member)
                current_head = head_member.head_member
            except Member.DoesNotExist:
                break

    def __str__(self):
        return f"{self.user.user.username} - Right Team ({self.team_members})"

    class Meta:
        verbose_name = "Right Team"
        verbose_name_plural = "Right Teams"

class IncomeHistory(models.Model):
    INCOME_TYPE_CHOICES = [
        ('direct_income', 'Direct Income'),
        ('level_income', 'Level Income'),
        ('matching_income', 'Matching Income'),
        ('resale_income', 'Resale Income'),
        ('royalty_income', 'Royalty Income'),
        ('reward_income', 'Reward Income'),
    ]

    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name='income_history')
    income_type = models.CharField(max_length=20, choices=INCOME_TYPE_CHOICES)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    description = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.member.user.username} - {self.income_type} - ₹{self.amount}"

    class Meta:
        verbose_name = "Income History"
        verbose_name_plural = "Income Histories"
        ordering = ['-created_at']

class RechargeTransaction(models.Model):
    STATUS_CHOICES = [
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('pending', 'Pending'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='recharge_transactions')
    mobile_no = models.CharField(max_length=15)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    company_name = models.CharField(max_length=50)
    order_id = models.CharField(max_length=20, unique=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    response_data = models.TextField(null=True, blank=True)
    recharge_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.mobile_no} - ₹{self.amount}"

    class Meta:
        verbose_name = "Recharge Transaction"
        verbose_name_plural = "Recharge Transactions"
        ordering = ['-recharge_date']

class WalletTransaction(models.Model):
    TRANSACTION_TYPE_CHOICES = [
        ('credit', 'Credit'),
        ('debit', 'Debit'),
        ('transfer_in', 'Transfer In'),
        ('transfer_out', 'Transfer Out'),
        ('withdrawal', 'Withdrawal'),
        ('recharge', 'Recharge'),
    ]

    user = models.ForeignKey(Member, on_delete=models.CASCADE, related_name='wallet_transactions')
    transaction_type = models.CharField(max_length=15, choices=TRANSACTION_TYPE_CHOICES)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    balance_after = models.DecimalField(max_digits=15, decimal_places=2)
    description = models.TextField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.user.username} - {self.transaction_type} - ₹{self.amount}"

    class Meta:
        verbose_name = "Wallet Transaction"
        verbose_name_plural = "Wallet Transactions"
        ordering = ['-timestamp']

class PaymentRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    REQUEST_TYPE_CHOICES = [
        ('withdrawal', 'Withdrawal'),
        ('bank_transfer', 'Bank Transfer'),
        ('upi_transfer', 'UPI Transfer'),
    ]

    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name='payment_requests')
    request_type = models.CharField(max_length=20, choices=REQUEST_TYPE_CHOICES, default='withdrawal')
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    wallet_balance_before = models.DecimalField(max_digits=15, decimal_places=2)
    
    # Bank details
    bank_name = models.CharField(max_length=100, null=True, blank=True)
    account_number = models.CharField(max_length=20, null=True, blank=True)
    ifsc_code = models.CharField(max_length=15, null=True, blank=True)
    account_holder_name = models.CharField(max_length=100, null=True, blank=True)
    
    # UPI details
    upi_id = models.CharField(max_length=100, null=True, blank=True)
    
    # Request details
    description = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='pending')
    request_date = models.DateTimeField(auto_now_add=True)
    
    # Admin actions
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_payments')
    approval_date = models.DateTimeField(null=True, blank=True)
    admin_notes = models.TextField(null=True, blank=True)
    rejection_reason = models.TextField(null=True, blank=True)
    
    # Transaction reference
    transaction_id = models.CharField(max_length=50, null=True, blank=True)
    completed_date = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.member.user.username} - {self.request_type} - ₹{self.amount} ({self.status})"

    class Meta:
        verbose_name = "Payment Request"
        verbose_name_plural = "Payment Requests"
        ordering = ['-request_date']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['request_date']),
            models.Index(fields=['member']),
        ]

    def save(self, *args, **kwargs):
        """Override save method to ensure account balance is updated correctly."""
        if self.pk is None:
            # This is a new request, set the initial wallet balance before the request
            self.wallet_balance_before = self.member.wallet_balance
        elif self.status == 'approved' and self.wallet_balance_before != self.member.wallet_balance:
            # If the request is being approved, ensure the wallet balance is updated
            self.wallet_balance_before = self.member.wallet_balance
        super().save(*args, **kwargs)
        # Update the member's wallet balance if the request is approved
        if self.status == 'approved':
            if self.member.wallet_balance < self.amount:
                raise ValueError("Wallet balance is insufficient for this withdrawal request.")
            else:
                # Deduct the amount from the member's wallet balance
                self.member.wallet_balance -= self.amount
                self.member.total_withdrawal += self.amount
                # Ensure the member's wallet balance does not go negative
                self.member.save(update_fields=['wallet_balance', 'total_withdrawal'])
                
                self.wallet_balance_before = self.member.wallet_balance
                self.status = 'completed'
                self.admin_notes = "Payment request approved."
                self.completed_date = timezone.now()
                self.save(update_fields=['wallet_balance_before', 'status', 'admin_notes', 'completed_date'])
                
                # Log the wallet transaction
                WalletTransaction.objects.create(
                    user=self.member,
                    transaction_type='withdrawal',
                    amount=self.amount,
                    balance_after=self.member.wallet_balance,
                    description=f"Payment request approved - {self.request_type}"
                )
            
        elif self.status == 'cancelled':
            self.delete()