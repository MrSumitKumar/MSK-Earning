# Django signals for MLM app
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.db import transaction


@receiver(post_save, sender=User)
def create_member_profile(sender, instance, created, **kwargs):
    """Create member profile when a new user is created"""
    if created:
        try:
            # Only create if it doesn't exist and we're not in a manual creation process
            if not hasattr(instance, 'mlm_profile'):
                from .models import Member
                Member.objects.get_or_create(user=instance)
        except Exception:
            pass


def create_team_structures_for_member(member):
    """Create team structures for a member (called manually)"""
    try:
        from .models import DirectTeam, LeftTeam, RightTeam
        DirectTeam.objects.get_or_create(user=member)
        LeftTeam.objects.get_or_create(user=member)
        RightTeam.objects.get_or_create(user=member)
    except Exception:
        pass