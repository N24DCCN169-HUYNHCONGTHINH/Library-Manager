import json
from io import BytesIO
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError
from django.core.mail import EmailMultiAlternatives
from django.test import SimpleTestCase, override_settings
from .email_backend import ResendEmailBackend, EmailDeliveryError


@override_settings(RESEND_API_KEY="test-key")
class ResendBackendTests(SimpleTestCase):
    @patch("apps.core.email_backend.urlopen")
    def test_payload_and_stable_idempotency(self, send):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b'{"id":"accepted"}'
        send.return_value = response
        message = EmailMultiAlternatives("Test", "Plain", "sender@example.invalid", ["reader@example.invalid"])
        message.attach_alternative("<p>HTML</p>", "text/html")
        backend = ResendEmailBackend()
        self.assertEqual(backend.send_messages([message]), 1)
        first = send.call_args.args[0]
        payload = json.loads(first.data)
        self.assertEqual(payload["text"], "Plain")
        self.assertEqual(payload["html"], "<p>HTML</p>")
        self.assertEqual(first.get_header("User-agent"), "LibraryHub/1.0")
        backend.send_messages([message])
        self.assertEqual(first.get_header("Idempotency-key"), send.call_args.args[0].get_header("Idempotency-key"))

    @patch("apps.core.email_backend.urlopen")
    def test_rejection_is_not_counted_or_leaked(self, send):
        send.side_effect = HTTPError("https://api.resend.com/emails", 403, "private details", {}, None)
        message = EmailMultiAlternatives("Test", "secret body", "s@example.invalid", ["r@example.invalid"])
        with self.assertRaisesMessage(EmailDeliveryError, "HTTP 403") as raised:
            ResendEmailBackend().send_messages([message])
        self.assertNotIn("private details", str(raised.exception))
        self.assertEqual(ResendEmailBackend(fail_silently=True).send_messages([message]), 0)

    @patch("apps.core.email_backend.urlopen")
    def test_sender_domain_error_is_actionable_without_sensitive_text(self, send):
        send.side_effect = HTTPError("https://api.resend.com/emails", 403, "Forbidden", {},
            BytesIO(b'{"message":"The secret.example domain is not verified; private data"}'))
        message = EmailMultiAlternatives("Test", "private body", "s@example.invalid", ["r@example.invalid"])
        with self.assertLogs("apps.core.email_backend", level="WARNING") as captured:
            with self.assertRaises(EmailDeliveryError) as raised:
                ResendEmailBackend().send_messages([message])
        self.assertIn("DEFAULT_FROM_EMAIL", raised.exception.public_message)
        self.assertNotIn("private", str(captured.output))
        self.assertNotIn("secret.example", raised.exception.public_message)
