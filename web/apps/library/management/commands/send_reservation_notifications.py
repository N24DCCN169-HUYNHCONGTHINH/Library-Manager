from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.library.models import Reservation, ReservationNotification


class Command(BaseCommand):
    help = "Send pending ready-for-pickup email notices; failed notices remain available for retry."

    def handle(self, *args, **options):
        from apps.core.models import SystemConfiguration
        if SystemConfiguration.objects.filter(pk=1, notifications_enabled=False).exists():
            self.stdout.write("Thông báo nghiệp vụ đang tắt.")
            return
        sent = failed = 0
        ids = ReservationNotification.objects.filter(sent_at__isnull=True,
            reservation__status=Reservation.Status.READY,
            reservation__expires_at__gt=timezone.now()).values_list("pk", flat=True)
        for notice_id in list(ids):
            with transaction.atomic():
                notice = ReservationNotification.objects.select_for_update().get(pk=notice_id)
                reservation = Reservation.objects.select_related("reader__user", "book").defer('book__cover_image').get(pk=notice.reservation_id)
                if notice.sent_at or reservation.status != Reservation.Status.READY or reservation.expires_at <= timezone.now():
                    continue
                notice.attempts += 1
                try:
                    if not reservation.reader.user.email:
                        raise ValueError("missing recipient")
                    count = send_mail("Sách đặt trước đã sẵn sàng",
                        f"Sách: {reservation.book.title}\nMã bạn đọc: {reservation.reader.reader_number}\n"
                        f"Hạn nhận: {timezone.localtime(reservation.expires_at):%d/%m/%Y %H:%M}.\n"
                        "Vui lòng xem yêu cầu trong cổng độc giả và đến quầy nhận sách.",
                        None, [reservation.reader.user.email], fail_silently=False)
                    if count != 1:
                        raise ValueError("mail not accepted")
                except Exception:
                    notice.last_error = "Không gửi được email; kiểm tra địa chỉ và cấu hình thư trước khi thử lại."
                    failed += 1
                else:
                    notice.sent_at = timezone.now()
                    notice.last_error = ""
                    sent += 1
                notice.save(update_fields=["sent_at", "last_error", "attempts"])
        self.stdout.write(f"Sent {sent}; failed {failed}. Pickup notices remain visible in the reader portal.")
