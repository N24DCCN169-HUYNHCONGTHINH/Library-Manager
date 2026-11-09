from datetime import timedelta

from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.library.models import Loan, LoanNotification
from apps.library.services import prepare_loan_notifications


class Command(BaseCommand):
    help = "Prepare due reminders; sending real email requires --send."

    def add_arguments(self, parser):
        parser.add_argument("--send", action="store_true", help="Send/retry pending email reminders.")

    def handle(self, *args, **options):
        from apps.core.models import SystemConfiguration
        config = SystemConfiguration.objects.filter(pk=1).first()
        reminder_days = config.reminder_days if config else 3
        today = timezone.localdate()
        prepared = prepare_loan_notifications(reminder_days)
        sent = failed = 0
        if options["send"] and (config is None or config.notifications_enabled):
            # Serialize delivery per notice. A crash after provider acceptance can still
            # cause a retry; this is an outbox, not an exactly-once email guarantee.
            ids = LoanNotification.objects.filter(sent_at__isnull=True, reminder_date__gte=today - timedelta(days=1)).values_list("pk", flat=True)
            for pk in list(ids):
                with transaction.atomic():
                    notice = LoanNotification.objects.select_for_update().select_related("loan__reader__user", "loan__copy__book").defer('loan__copy__book__cover_image').get(pk=pk)
                    loan = notice.loan
                    if notice.sent_at or loan.status != Loan.Status.OPEN or loan.due_at != notice.due_at:
                        continue
                    notice.attempts += 1
                    try:
                        if not loan.reader.user.email:
                            raise ValueError("missing recipient")
                        count = send_mail(f"Thư viện: {notice.get_kind_display()}",
                            f"Sách: {loan.copy.book.title}\nHạn trả: {timezone.localtime(loan.due_at):%d/%m/%Y %H:%M}.\n"
                            "Vui lòng xem chi tiết trong cổng độc giả hoặc liên hệ quầy thư viện.",
                            None, [loan.reader.user.email], fail_silently=False)
                        if count != 1:
                            raise ValueError("not accepted")
                    except Exception:
                        notice.last_error = "Không gửi được email; kiểm tra địa chỉ và cấu hình thư."
                        failed += 1
                    else:
                        notice.sent_at = timezone.now()
                        notice.last_error = ""
                        sent += 1
                    notice.save(update_fields=["attempts", "sent_at", "last_error"])
        self.stdout.write(f"Prepared {prepared}; sent {sent}; failed {failed}.")
