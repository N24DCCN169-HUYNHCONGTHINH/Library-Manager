from django.core.management.base import BaseCommand

from apps.library.services import expire_ready_reservations


class Command(BaseCommand):
    help = "Expire reservation holds past their deadline and assign the next eligible reader."

    def handle(self, *args, **options):
        count = expire_ready_reservations()
        self.stdout.write(self.style.SUCCESS(f"Expired {count} reservation hold(s)."))
