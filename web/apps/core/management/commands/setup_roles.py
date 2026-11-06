from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand, CommandError
from apps.core.roles import ROLE_PERMISSIONS

class Command(BaseCommand):
    help = "Synchronize five least-privilege roles and the legacy compatibility group."
    ROLE_NAMES = tuple(ROLE_PERMISSIONS)
    def handle(self, *args, **options):
        index = {f"{p.content_type.app_label}.{p.codename}": p for p in Permission.objects.select_related("content_type")}
        missing = set().union(*ROLE_PERMISSIONS.values()) - index.keys()
        if missing:
            raise CommandError("Run migrations first; missing permissions: " + ", ".join(sorted(missing)))
        for name, permissions in ROLE_PERMISSIONS.items():
            group, _ = Group.objects.get_or_create(name=name)
            group.permissions.set([index[key] for key in sorted(permissions)])
            self.stdout.write(f"Role '{name}': synchronized.")
