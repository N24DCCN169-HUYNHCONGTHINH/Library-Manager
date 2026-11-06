"""Transactional email over HTTPS; never log credentials or message bodies."""
import json
import ssl
import uuid
import logging
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import certifi
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.mail.backends.base import BaseEmailBackend


class EmailDeliveryError(RuntimeError):
    public_message = "Không kết nối được dịch vụ email. Vui lòng thử lại sau."


logger = logging.getLogger(__name__)


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
                                   "Accept": "application/json", "User-Agent": "LibraryHub/1.0",
                                   "Idempotency-Key": message._resend_idempotency_key}, method="POST")
        try:
            with urlopen(request, timeout=15, context=ssl.create_default_context(cafile=certifi.where())) as response:
                result = json.loads(response.read())
                if not isinstance(result, dict) or not result.get("id"):
                    raise EmailDeliveryError("Email provider did not confirm acceptance.")
        except HTTPError as exc:
            # Read a bounded response only to classify it. Never expose its text,
            # which can contain recipient addresses or other sensitive data.
            try:
                details = json.loads(exc.read(8192))
                explanation = str(details.get("message", "")).lower() if isinstance(details, dict) else ""
            except (ValueError, OSError, AttributeError):
                explanation = ""
            category = "provider_rejected"
            advice = "Dịch vụ email từ chối gửi thư. Vui lòng kiểm tra cấu hình trên Render và Resend."
            if exc.code == 401 or "api key" in explanation:
                category = "api_key"
                advice = "Khóa Resend chưa hợp lệ hoặc chưa có quyền gửi. Kiểm tra RESEND_API_KEY trên Render."
            elif "domain" in explanation and ("verif" in explanation or "from" in explanation):
                category = "sender_domain"
                advice = "Địa chỉ gửi chưa khớp tên miền đã xác minh. Kiểm tra DEFAULT_FROM_EMAIL trên Render."
            elif exc.code == 429:
                category = "rate_limit"
                advice = "Dịch vụ email đang giới hạn lượt gửi. Vui lòng chờ rồi thử lại."
            logger.warning("Resend delivery rejected: HTTP %s; category=%s", exc.code, category)
            error = EmailDeliveryError(f"Email provider rejected request (HTTP {exc.code}).")
            error.public_message = f"{advice} (HTTP {exc.code}; {category})"
            raise error from None
        except (URLError, TimeoutError, OSError, ValueError):
            logger.warning("Resend delivery failed: transport_or_response_error")
            raise EmailDeliveryError("Could not confirm email delivery with provider.") from None
