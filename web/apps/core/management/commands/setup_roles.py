from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create the standard library roles and synchronize their least-privilege permissions."

    ROLE_NAMES = ("reader", "librarian", "circulation_staff", "cataloger", "library_manager", "system_admin")

    def handle(self, *args, **options):
        groups = {}
        for name in self.ROLE_NAMES:
            groups[name], created = Group.objects.get_or_create(name=name)
            self.stdout.write(f"Role '{name}': {'created' if created else 'synchronized'}.")

        permission_index = {
            f"{permission.content_type.app_label}.{permission.codename}": permission
            for permission in Permission.objects.select_related("content_type").all()
        }

        core_roles = {
            "reader": set(),
            "cataloger": set(),
            "circulation_staff": {"view_readerprofile"},
            "librarian": {"view_readerprofile", "verify_reader_membership", "view_accountsecurity", "verify_account_email"},
            "library_manager": {
                "view_readerprofile", "add_readerprofile", "change_readerprofile",
                "verify_reader_membership", "suspend_reader", "view_accountsecurity",
                "verify_account_email", "issue_account_invitation", "manage_account_lifecycle",
                "revoke_totp_device", "view_accountsecurityevent", "view_accountinvitation",
                "manage_account_invitations", "view_emailchangeverification",
            },
            "system_admin": {"view_accountsecurity", "revoke_totp_device", "view_accountsecurityevent"},
        }

        catalog_perms = {
            "view_book", "add_book", "change_book",
            "view_bookcopy", "add_bookcopy", "change_bookcopy",
            "view_librarybranch",
        }
        circulation_view = {
            "view_book", "view_bookcopy", "view_librarybranch", "view_loan", "view_loanrenewal",
            "view_loanevent", "view_reservation", "view_fine", "view_finepayment",
            "view_readerrestriction", "view_damagecase",
        }
        circulation_actions = {
            "checkout_loan", "return_loan", "renew_loan", "collect_finepayment",
        }

        role_app_perms = {
            "reader": set(),
            "cataloger": catalog_perms,
            "circulation_staff": circulation_view | circulation_actions,
            # Legacy librarian is a working librarian, not a manager.
            "librarian": catalog_perms | circulation_view | circulation_actions,
            "library_manager": {
                p.codename
                for p in Permission.objects.select_related("content_type").filter(content_type__app_label="library")
                if not p.codename.startswith("delete_")
                and not (
                    p.content_type.model in {"loan", "loanrenewal", "loanevent", "reservation", "fine", "finepayment"}
                    and p.codename.split("_", 1)[0] in {"add", "change"}
                )
            },
            # Technical administrators can inspect accounts/groups but do not
            # receive business-data or day-to-day library operation rights.
            "system_admin": {"auth.view_user", "auth.view_group"},
        }

        role_permissions = {}
        for name in self.ROLE_NAMES:
            full_names = {f"core.{codename}" for codename in core_roles[name]}
            if name == "system_admin":
                full_names.update({"auth.view_user", "auth.view_group"})
            else:
                full_names.update(f"library.{codename}" for codename in role_app_perms[name])
            if name == "library_manager":
                full_names.add("auth.view_user")
            role_permissions[name] = [permission_index[key] for key in full_names if key in permission_index]

        for name, group in groups.items():
            group.permissions.set(role_permissions[name])
