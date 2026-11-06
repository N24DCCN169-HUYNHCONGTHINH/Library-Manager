from django.contrib.auth import get_user_model

from .models import AccountSecurity


def testing_lockout_exemption(request, credentials=None):
    """Explicit per-account exception; never exempts all staff/admin roles."""
    username = (credentials or {}).get(get_user_model().USERNAME_FIELD)
    if not isinstance(username, str) or not username:
        return False
    return AccountSecurity.objects.filter(
        user__username=username, user__is_active=True, password_lockout_exempt=True,
    ).exists()
