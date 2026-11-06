"""One policy for provisioning, account delegation and the role inspector."""
ROLE_CHOICES = [("reader", "Độc giả"), ("cataloger", "Nhân viên biên mục"), ("circulation_staff", "Nhân viên lưu thông"), ("librarian", "Thủ thư"), ("system_admin", "Quản trị viên hệ thống")]
LEGACY_ROLE = "library_manager"
ALL_ROLES = {r[0] for r in ROLE_CHOICES} | {LEGACY_ROLE}
PRIVILEGED = {"librarian", LEGACY_ROLE, "system_admin"}

def canonical_roles(names):
    return {"librarian" if name == LEGACY_ROLE else name for name in names}

def can_assign_roles(actor):
    return actor.is_superuser or actor.has_perm("core.assign_account_roles")

def protected_user(user):
    return user.is_superuser or user.groups.filter(name__in=PRIVILEGED).exists()

def can_manage_target(actor, subject):
    if actor.pk == subject.pk: return True
    if subject.is_superuser: return actor.is_superuser
    return can_assign_roles(actor) or not protected_user(subject)

CATALOG = {"library." + p for p in ("view_book", "add_book", "change_book", "delete_book", "view_bookcopy", "add_bookcopy", "change_bookcopy", "view_librarybranch", "manage_catalog", "manage_bookcopy")}
CIRCULATION_VIEW = {"library."+p for p in ("view_book", "view_bookcopy", "view_librarybranch", "view_loan", "view_loanrenewal", "view_loanevent", "view_reservation", "view_fine", "view_finepayment", "view_readerrestriction", "view_damagecase", "view_loannotification")}
CIRCULATION_ACTIONS = {"library."+p for p in ("checkout_loan", "return_loan", "renew_loan", "collect_finepayment", "manage_reservation")}
READERS = {"core."+p for p in ("view_readerprofile", "add_readerprofile", "change_readerprofile", "verify_reader_membership", "suspend_reader", "invite_reader")}
ACCOUNT_MANAGEMENT = {"auth.view_user"} | {"core."+p for p in ("view_accountsecurity", "issue_account_invitation", "manage_account_lifecycle", "revoke_totp_device", "view_accountsecurityevent", "view_accountinvitation", "manage_account_invitations", "view_emailchangeverification")}
POLICY = {"library."+action+"_"+model for action in ("view", "add", "change") for model in ("circulationpolicy", "libraryhours", "libraryclosure", "librarybranch")}
BUSINESS_APPROVAL = {"library."+p for p in ("approve_finepayment", "approve_damagecase", "manage_reader_restrictions", "view_system_reports", "view_damagecase", "change_damagecase")}
ROLE_PERMISSIONS = {
    "reader": set(),
    "cataloger": CATALOG,
    "circulation_staff": CIRCULATION_VIEW | CIRCULATION_ACTIONS | READERS,
    "librarian": CATALOG | CIRCULATION_VIEW | CIRCULATION_ACTIONS | READERS | POLICY | BUSINESS_APPROVAL,
    "system_admin": ACCOUNT_MANAGEMENT | {"auth.view_group", "core.assign_account_roles", "core.manage_system_operations"},
}
# Kept only for existing installations. Never offered as a sixth new role.
ROLE_PERMISSIONS[LEGACY_ROLE] = ROLE_PERMISSIONS["librarian"] | ACCOUNT_MANAGEMENT | {"core.verify_account_email"}
