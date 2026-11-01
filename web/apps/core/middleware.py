from django.shortcuts import redirect


class RequirePasswordChangeMiddleware:
    """Block authenticated users with temporary credentials until they change them."""

    allowed_prefixes = (
        "/accounts/password_change/",
        "/accounts/password_change/done/",
        "/accounts/logout/",
        "/static/",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user and user.is_authenticated and not any(request.path_info.startswith(p) for p in self.allowed_prefixes):
            security = getattr(user, "security_profile", None)
            if security and security.must_change_password:
                return redirect("password_change")
        return self.get_response(request)
