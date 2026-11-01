def library_roles(request):
    user = request.user
    if not user.is_authenticated:
        return {"library_roles": {"librarian": False, "reader": False}}
    if user.is_superuser:
        return {"library_roles": {"librarian": True, "reader": False, "can_circulate": True, "can_catalog": True, "staff_roles": ["system_admin"]}}
    roles = set(user.groups.values_list("name", flat=True))
    staff_roles = {"librarian", "circulation_staff", "cataloger", "library_manager", "system_admin"}
    return {
        "library_roles": {
            "librarian": bool(roles & staff_roles),
            "reader": "reader" in roles,
            "can_circulate": user.has_perm("library.view_loan") and user.has_perm("library.view_fine"),
            "can_catalog": user.has_perm("library.view_book"),
            "staff_roles": sorted(roles & staff_roles),
        }
    }
