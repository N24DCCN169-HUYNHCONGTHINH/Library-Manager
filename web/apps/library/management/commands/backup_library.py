from django.core.management.base import BaseCommand, CommandError
from apps.library.backup import create_backup


class Command(BaseCommand):
    help = "Create a consistent application-data and media backup without sessions or lockout records."

    def add_arguments(self, parser):
        parser.add_argument("--output", required=True)

    def handle(self, *args, **options):
        try:
            manifest = create_backup(options["output"])
        except Exception as exc:
            raise CommandError("Backup failed: " + type(exc).__name__) from exc
        self.stdout.write(f"Backup created; {sum(manifest['counts'].values())} application records. Treat archive as sensitive.")
