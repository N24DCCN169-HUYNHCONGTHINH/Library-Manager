from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.core.models import ReaderProfile
from apps.library.models import CirculationPolicy


class Command(BaseCommand):
    help = "Create the initial Day 1 circulation policy rows without replacing existing policy."

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True, help="Existing staff username to record as policy creator.")

    def handle(self, *args, **options):
        user_model = get_user_model()
        try:
            actor = user_model.objects.get(username=options["username"], is_staff=True, is_active=True)
        except user_model.DoesNotExist as exc:
            raise CommandError("Username must belong to an existing active staff account.") from exc

        limits = {
            ReaderProfile.ReaderType.STUDENT: (5, 14),
            ReaderProfile.ReaderType.FACULTY: (10, 30),
            ReaderProfile.ReaderType.EMPLOYEE: (10, 30),
        }
        restricted_types = {"rare", "periodical", "thesis"}
        created_count = 0
        for reader_type, (quota, loan_days) in limits.items():
            for material_type, _label in CirculationPolicy.MaterialType.choices:
                _, created = CirculationPolicy.objects.get_or_create(
                    reader_type=reader_type,
                    material_type=material_type,
                    version=1,
                    defaults={
                        "effective_from": timezone.localdate(),
                        "allow_home_loan": material_type not in restricted_types,
                        "max_active_loans": quota,
                        "loan_days": loan_days,
                        "max_renewals": 1,
                        "renewal_days": 7,
                        "overdue_rate_per_day": 1000,
                        "overdue_fine_cap": 30000,
                        "created_by": actor,
                    },
                )
                created_count += int(created)
        self.stdout.write(self.style.SUCCESS(f"Created {created_count} initial policy rows; existing policies were left unchanged."))
