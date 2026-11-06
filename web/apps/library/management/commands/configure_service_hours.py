from datetime import time
import json

from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.library.models import LibraryHours


class Command(BaseCommand):
    help = "Apply the service hours confirmed on 2026-11-06; no holidays are invented."

    def add_arguments(self, parser):
        parser.add_argument("--actor", required=True)
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        actor = get_user_model().objects.filter(username=options["actor"], is_active=True).first()
        if not actor or not actor.has_perm("library.change_libraryhours"):
            raise CommandError("An active manager with change_libraryhours permission is required.")
        schedule = [(day, time(8), time(21 if day < 5 else 18 if day == 5 else 16)) for day in range(7)]
        if not options["apply"]:
            self.stdout.write("Preview: Mon–Fri 08:00–21:00; Sat 08:00–18:00; Sun 08:00–16:00. Use --apply to save.")
            return
        with transaction.atomic():
            for day, opens, closes in schedule:
                row, created = LibraryHours.objects.select_for_update().get_or_create(weekday=day)
                before = {"is_open": row.is_open, "opens_at": str(row.opens_at), "closes_at": str(row.closes_at)}
                after = {"is_open": True, "opens_at": str(opens), "closes_at": str(closes)}
                if not created and before == after:
                    continue
                row.is_open, row.opens_at, row.closes_at = True, opens, closes
                row.full_clean()
                row.save()
                LogEntry.objects.create(user=actor, content_type=ContentType.objects.get_for_model(row),
                    object_id=str(row.pk), object_repr=str(row), action_flag=CHANGE,
                    change_message=json.dumps({"reason": "Giờ phục vụ do chủ dự án xác nhận ngày 06/11/2026", "before": before, "after": after}, ensure_ascii=False))
        self.stdout.write("Saved seven weekdays with audit. Holiday dates remain unchanged.")
