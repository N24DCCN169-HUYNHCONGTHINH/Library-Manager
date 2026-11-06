from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from apps.library.hcm_demo import export_dataset, seed_dataset


class Command(BaseCommand):
    help = "Export a sourced real-library directory and a separate synthetic dataset; optionally add tagged demo records."

    def add_arguments(self, parser):
        parser.add_argument("--output", required=True)
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--username", help="Existing active library manager to record as demo creator")

    def handle(self, *args, **options):
        actor = None
        if options["apply"]:
            actor = get_user_model().objects.filter(username=options["username"], is_active=True).first()
            if not actor or not actor.has_perm("library.add_book") or not actor.has_perm("core.add_readerprofile"):
                raise CommandError("An active library manager --username is required.")
        try:
            data = export_dataset(options["output"])
            if actor:
                seed_dataset(actor, data)
        except ValidationError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write("Exported: " + str(Path(options["output"]).resolve() / "index.html"))
        self.stdout.write(str(data["counts"]))
        self.stdout.write("Applied to application database." if actor else "Export only; database unchanged.")
