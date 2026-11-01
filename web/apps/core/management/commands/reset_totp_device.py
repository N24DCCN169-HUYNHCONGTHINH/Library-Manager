from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.core.lifecycle import revoke_totp_devices


class Command(BaseCommand):
    help = "Revoke a staff member's authenticator devices so they can enroll again."

    def add_arguments(self, parser):
        parser.add_argument("username")
        parser.add_argument("--actor", required=True, help="Active staff username authorizing and recording the recovery.")
        parser.add_argument("--reason", default="Staff member reported a lost authenticator device.")
        parser.add_argument("--yes", action="store_true", help="Confirm device revocation without an interactive prompt.")

    def handle(self, *args, **options):
        try:
            user = get_user_model().objects.get(username=options["username"])
        except get_user_model().DoesNotExist as exc:
            raise CommandError("No account found with that username.") from exc
        try:
            actor = get_user_model().objects.get(username=options["actor"], is_active=True)
        except get_user_model().DoesNotExist as exc:
            raise CommandError("No active authorizing account found.") from exc
        if not actor.is_superuser and not actor.has_perm("core.revoke_totp_device"):
            raise CommandError("The authorizing account does not have permission to revoke authenticator devices.")
        from django_otp.plugins.otp_totp.models import TOTPDevice
        count = TOTPDevice.objects.filter(user=user).count()
        if not options["yes"]:
            answer = input(f"Revoke {count} authenticator device(s) and all sessions for {user.get_username()}? Type 'yes': ")
            if answer != "yes":
                self.stdout.write("No devices were changed.")
                return
        try:
            count, sessions = revoke_totp_devices(subject=user, actor=actor, reason=options["reason"], channel="management_command")
        except PermissionError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(f"Revoked {count} authenticator device(s) and expired {sessions} session(s). The user must enroll again."))
