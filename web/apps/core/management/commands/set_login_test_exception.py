from axes.utils import reset
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.core.lifecycle import record_security_event
from apps.core.models import AccountSecurity, AccountSecurityEvent


class Command(BaseCommand):
    help = "Enable or revoke an explicit account's password-lockout testing exception."

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True)
        parser.add_argument("--actor", required=True)
        parser.add_argument("--reason", required=True)
        parser.add_argument("--mode", choices=["enable", "disable"], required=True)

    def handle(self, *args, **options):
        actor = get_user_model().objects.filter(username=options["actor"], is_active=True).first()
        user = get_user_model().objects.filter(username=options["username"], is_active=True).first()
        if not actor or not actor.has_perm("core.manage_account_lifecycle") or not user or not options["reason"].strip():
            raise CommandError("Cần tài khoản/quản lý hợp lệ, quyền quản lý tài khoản và lý do.")
        enabled = options["mode"] == "enable"
        with transaction.atomic():
            security = AccountSecurity.objects.select_for_update().get(user=user)
            old = security.password_lockout_exempt
            security.password_lockout_exempt = enabled
            security.save(update_fields=["password_lockout_exempt", "updated_at"])
            record_security_event(user, AccountSecurityEvent.Kind.LOCKOUT_EXCEPTION, actor,
                {"before": old, "after": enabled, "source": "owner_testing_request"}, reason=options["reason"])
            if enabled:
                reset(username=user.get_username())
        self.stdout.write(f"Password lockout exception {'enabled' if enabled else 'disabled'} for the selected account only.")
