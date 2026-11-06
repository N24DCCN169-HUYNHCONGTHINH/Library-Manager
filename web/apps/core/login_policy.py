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


def configured_failure_limit(request, credentials=None):
    from .models import SystemConfiguration
    value=SystemConfiguration.objects.filter(pk=1).values_list("login_failure_limit",flat=True).first()
    return value if value in {3,4,5} else 5

def configured_cooloff(request):
    from datetime import timedelta
    from .models import SystemConfiguration
    value=SystemConfiguration.objects.filter(pk=1).values_list("lockout_minutes",flat=True).first()
    return timedelta(minutes=value if value in {15,30,60} else 15)
