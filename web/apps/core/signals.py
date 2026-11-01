from django.conf import settings
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .lifecycle import record_security_event
from .models import AccountSecurity, AccountSecurityEvent


@receiver(pre_save, sender=settings.AUTH_USER_MODEL)
def remember_user_email(sender, instance, **kwargs):
    if instance.pk:
        instance._security_previous_email = sender._default_manager.filter(pk=instance.pk).values_list("email", flat=True).first()
    else:
        instance._security_previous_email = None


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_account_security_profile(sender, instance, created, **kwargs):
    if created:
        AccountSecurity.objects.get_or_create(user=instance)
        return
    old_email = getattr(instance, "_security_previous_email", instance.email)
    if old_email is not None and (old_email or "").casefold() != (instance.email or "").casefold():
        security, _ = AccountSecurity.objects.get_or_create(user=instance)
        security.verified_email = ""
        security.email_verified_at = None
        security.save(update_fields=("verified_email", "email_verified_at", "updated_at"))
        record_security_event(
            instance,
            AccountSecurityEvent.Kind.EMAIL_CHANGED,
            getattr(instance, "_security_actor", None),
            {"reverification_required": True},
        )
