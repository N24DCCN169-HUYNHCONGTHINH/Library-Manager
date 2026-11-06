"""Transactional email over HTTPS; never log credentials or message bodies."""
import json
import ssl
import uuid
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import certifi
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.mail.backends.base import BaseEmailBackend


class EmailDeliveryError(RuntimeError):
    pass


class ResendEmailBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        sent = 0
        for message in email_messages or []:
            if not message.recipients():
                continue
            try:
                self._send(message)
                sent += 1
            except (EmailDeliveryError, ImproperlyConfigured, ValueError):
                if not self.fail_silently:
                    raise
        return sent

    def _send(self, message):
        key = getattr(settings, "RESEND_API_KEY", "").strip()
        if not key:
            raise ImproperlyConfigured("RESEND_API_KEY is required.")
        message.message()  # Django validates addresses and prevents header injection.
        if message.attachments or message.extra_headers:
            raise ValueError("Attachments and custom headers are not supported by this backend.")
        payload = {"from": message.from_email, "subject": message.subject}
        for name in ("to", "cc", "bcc", "reply_to"):
            value = getattr(message, name, None)
            if value:
                payload[name] = value
        payload["html" if message.content_subtype == "html" else "text"] = message.body
        for alternative in getattr(message, "alternatives", []):
            if alternative.mimetype == "text/html":
                payload["html"] = alternative.content
        # Reusing the same EmailMessage after a transient failure keeps its key.
        if not hasattr(message, "_resend_idempotency_key"):
            message._resend_idempotency_key = str(uuid.uuid4())
        request = Request("https://api.resend.com/emails", data=json.dumps(payload).encode("utf-8"),
                          headers={"Authorization": "Bearer " + key, "Content-Type": "application/json",
                                   "Idempotency-Key": message._resend_idempotency_key}, method="POST")
        try:
            with urlopen(request, timeout=15, context=ssl.create_default_context(cafile=certifi.where())) as response:
                result = json.loads(response.read())
                if not result.get("id"):
                    raise EmailDeliveryError("Email provider did not confirm acceptance.")
        except HTTPError as exc:
            raise EmailDeliveryError(f"Email provider rejected request (HTTP {exc.code}).") from None
        except (URLError, TimeoutError, OSError, ValueError):
            raise EmailDeliveryError("Could not confirm email delivery with provider.") from None
