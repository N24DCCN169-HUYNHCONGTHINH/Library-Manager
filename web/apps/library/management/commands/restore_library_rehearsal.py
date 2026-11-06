from django.core.management.base import BaseCommand, CommandError
from apps.library.backup import restore_rehearsal


class Command(BaseCommand):
    help = "Restore into a NEW isolated SQLite database and compare data; never replaces the live database."

    def add_arguments(self, parser):
        parser.add_argument("--backup", required=True)
        parser.add_argument("--output", required=True)

    def handle(self, *args, **options):
        try:
            result = restore_rehearsal(options["backup"], options["output"])
        except Exception as exc:
            raise CommandError("Restore rehearsal failed: " + str(exc)) from exc
        self.stdout.write("Restore verification: " + ("OK" if result["verified"] else "FAILED"))
