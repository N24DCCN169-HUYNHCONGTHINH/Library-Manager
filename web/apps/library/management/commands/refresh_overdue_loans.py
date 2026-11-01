from django.core.management.base import BaseCommand

from apps.library.services import refresh_overdue_loans


class Command(BaseCommand):
    help = "Update accruing overdue fines and apply the seven-day suspension threshold."

    def handle(self, *args, **options):
        count = refresh_overdue_loans()
        self.stdout.write(self.style.SUCCESS(f"Refreshed {count} overdue loan(s)."))
