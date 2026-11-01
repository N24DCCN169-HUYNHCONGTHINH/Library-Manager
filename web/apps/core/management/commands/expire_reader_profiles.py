from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.core.models import AccountSecurityEvent, ReaderProfile


class Command(BaseCommand):
    help = "Mark expired reader cards and record the automatic status transition."

    def handle(self, *args, **options):
        today = timezone.localdate()
        count = 0
        for profile in ReaderProfile.objects.filter(status=ReaderProfile.Status.ACTIVE, valid_until__lt=today).select_related("user").iterator():
            profile.status = ReaderProfile.Status.EXPIRED
            profile.save(update_fields=("status", "updated_at"))
            AccountSecurityEvent.objects.create(
                subject=profile.user,
                kind=AccountSecurityEvent.Kind.MEMBERSHIP_EXPIRED,
                details={"reader_number": profile.reader_number, "valid_until": profile.valid_until.isoformat()},
            )
            count += 1
        self.stdout.write(self.style.SUCCESS(f"Marked {count} expired reader card(s)."))
