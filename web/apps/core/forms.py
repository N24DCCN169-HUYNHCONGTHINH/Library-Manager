from django.contrib.auth.forms import PasswordResetForm
from django.core.exceptions import ObjectDoesNotExist


class VerifiedReaderEmailPasswordResetForm(PasswordResetForm):
    """Only send reset links to addresses confirmed by library staff."""

    def get_users(self, email):
        for user in super().get_users(email):
            try:
                security = user.security_profile
            except ObjectDoesNotExist:
                continue
            if security.email_is_verified:
                yield user
