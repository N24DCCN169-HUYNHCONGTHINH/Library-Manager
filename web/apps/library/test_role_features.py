from datetime import timedelta
from decimal import Decimal
from io import BytesIO
import json, uuid
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django_otp.plugins.otp_totp.models import TOTPDevice
from openpyxl import load_workbook
from . import tests as role_fixtures
from .models import Fine, FinePayment, PaymentOrder, FineWaiverRequest, Book, BookCopy
from .payments import start_order, signed
from .management_views import review_waiver
from .services import CirculationError

@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class RoleFeatureTests(TestCase):
    setUpTestData=role_fixtures.LibraryRoleAcceptanceTests.__dict__["setUpTestData"]
    make_user=role_fixtures.LibraryRoleAcceptanceTests.__dict__["make_user"]
    make_book=role_fixtures.LibraryRoleAcceptanceTests.__dict__["make_book"]
    make_loan=role_fixtures.LibraryRoleAcceptanceTests.__dict__["make_loan"]
    def setUp(self):
        self.librarian=self.make_user("new-librarian","librarian",staff=True)
        self.fine=Fine.objects.create(loan=self.loan_a,rate_per_day=1000,cap_amount=30000,accrued_amount=4000,status="due")
    def login(self,user,mfa=True):
        self.client.force_login(user)
        if mfa and user.groups.exclude(name="reader").exists():
            device=TOTPDevice.objects.create(user=user,name="test",confirmed=True)
            session=self.client.session;session["otp_device_id"]=device.persistent_id;session.save()
    def test_five_role_direct_urls_and_forged_posts(self):
        routes=[("library:book_add",[],{ "cataloger","librarian"}),("reader_list",[],{"circulation_staff","librarian"}),("account_list",[],{"system_admin"}),("operations",[],{"system_admin"}),("library:policies",[],{"librarian"})]
        users={"reader":self.reader_a,"cataloger":self.cataloger,"circulation_staff":self.circulation,"librarian":self.librarian,"system_admin":self.system_admin}
        for role,user in users.items():
            self.login(user)
            for name,args,allowed in routes:
                response=self.client.get(reverse(name,args=args))
                self.assertEqual(response.status_code,200 if role in allowed else 302 if role=="reader" else 403,(role,name))
            if role in {"cataloger","system_admin"}:
                self.assertEqual(self.client.post(reverse("library:circulation_desk"),{"action":"checkout","reader_number":self.profile_a.reader_number,"barcode":self.copy_a.barcode}).status_code,403)
    def test_managed_password_reset_requires_reauthentication_and_forces_change(self):
        self.login(self.system_admin)
        url = reverse("account_reset_password", args=[self.reader_a.pk])
        data = {
            "current_password": "incorrect", "new_password1": "Temporary-74-Book!",
            "new_password2": "Temporary-74-Book!", "reason": "Support request",
        }
        self.assertEqual(self.client.post(url, data).status_code, 200)
        self.reader_a.refresh_from_db()
        self.assertTrue(self.reader_a.check_password("Test-password-123!"))
        data["current_password"] = "Test-password-123!"
        self.assertRedirects(self.client.post(url, data), reverse("account_detail", args=[self.reader_a.pk]))
        self.reader_a.refresh_from_db()
        self.assertTrue(self.reader_a.check_password(data["new_password1"]))
        self.assertTrue(self.reader_a.security_profile.must_change_password)
        self.assertEqual(self.client.post(reverse("account_reset_password", args=[self.system_admin.pk]), data).status_code, 403)

    def test_bulk_archive_and_restore_preserve_original_login_status(self):
        self.reader_b.is_active = False
        self.reader_b.save(update_fields=["is_active"])
        self.login(self.system_admin)
        url = reverse("account_bulk")
        selected = [self.reader_a.pk, self.reader_b.pk]
        response = self.client.post(url, {"action": "archive", "account_id": selected, "reason": "Test"})
        self.assertRedirects(response, reverse("account_list"))
        self.assertNotContains(self.client.get(reverse("account_list")), self.reader_a.username)
        self.assertContains(self.client.get(reverse("account_list") + "?archived=1"), self.reader_a.username)
        for reader in (self.reader_a, self.reader_b):
            reader.refresh_from_db()
            self.assertFalse(reader.is_active)
        self.client.post(url, {"action": "restore", "account_id": selected, "reason": "Test"})
        self.reader_a.refresh_from_db()
        self.reader_b.refresh_from_db()
        self.assertTrue(self.reader_a.is_active)
        self.assertFalse(self.reader_b.is_active)
        self.assertNotContains(self.client.get(reverse("account_list") + "?archived=1"), self.reader_a.username)

    def test_staff_mfa_cannot_be_skipped_for_exports_or_operations(self):
        self.login(self.cataloger,mfa=False)
        self.assertEqual(self.client.get(reverse("library:reports"),{"kind":"inventory","format":"xlsx"}).status_code,302)
        self.login(self.system_admin,mfa=False)
        self.assertEqual(self.client.post(reverse("backup_download"),{}).status_code,302)
    def test_excel_csv_and_report_scope(self):
        today=timezone.localdate().isoformat();params={"kind":"inventory","start":today,"end":today,"format":"xlsx"}
        self.login(self.cataloger)
        response=self.client.get(reverse("library:reports"),params)
        self.assertEqual(response.status_code,200)
        workbook=load_workbook(BytesIO(response.content));self.assertEqual(workbook.active.cell(3,1).value,"Mã sách")
        response=self.client.get(reverse("library:reports"),params|{"format":"csv"})
        self.assertTrue(response.content.startswith(b"\xef\xbb\xbf"))
        self.assertEqual(self.client.get(reverse("library:reports"),params|{"kind":"summary"}).status_code,403)
        self.login(self.system_admin)
        self.assertEqual(self.client.get(reverse("library:reports"),params).status_code,403)
        self.login(self.librarian)
        response=self.client.get(reverse("library:reports"),params|{"kind":"summary","format":"xlsx"})
        self.assertEqual(response.status_code,200)
        self.assertIn("no-store",response.get("Cache-Control",""))
    def test_exports_escape_formula_injection(self):
        self.book_a.title="=HYPERLINK(\"https://bad.example\")";self.book_a.save()
        self.login(self.cataloger);today=timezone.localdate().isoformat()
        response=self.client.get(reverse("library:reports"),{"kind":"inventory","start":today,"end":today,"format":"xlsx"})
        workbook=load_workbook(BytesIO(response.content));values=list(workbook.active.values)
        self.assertTrue(any(str(row[1]).startswith("'=HYPERLINK") for row in values[3:]))
    def test_payment_simulation_never_changes_real_debt_and_is_idempotent(self):
        self.login(self.reader_a);key=uuid.uuid4()
        order=start_order(user=self.reader_a,fine_id=self.fine.pk,amount=Decimal(1000),channel="bank",request_key=key)
        again=start_order(user=self.reader_a,fine_id=self.fine.pk,amount=Decimal(1000),channel="bank",request_key=key)
        self.assertEqual(order.pk,again.pk)
        url=reverse("library:simulate_payment",args=[order.pk])
        self.assertEqual(self.client.get(url).status_code,405)
        self.client.post(url,{"result":"success"});self.client.post(url,{"result":"success"})
        order.refresh_from_db();self.assertEqual(order.state,"success")
        self.fine.refresh_from_db();self.assertEqual(self.fine.balance,4000);self.assertEqual(FinePayment.objects.count(),0)
    def test_payment_owner_protection_and_amount_tampering(self):
        order=start_order(user=self.reader_a,fine_id=self.fine.pk,amount=Decimal(1000),channel="momo",request_key=uuid.uuid4())
        self.login(self.reader_b)
        self.assertEqual(self.client.get(reverse("library:payment_detail",args=[order.pk])).status_code,404)
        self.assertEqual(self.client.post(reverse("library:simulate_payment",args=[order.pk]),{"result":"success"}).status_code,404)
        self.assertEqual(self.client.get(reverse("library:payment_start",args=[self.fine.pk])).status_code,404)
        with self.assertRaises(ValidationError): start_order(user=self.reader_a,fine_id=self.fine.pk,amount=Decimal(99999),channel="bank",request_key=uuid.uuid4())
    def test_momo_ipn_rejects_unsigned_wrong_amount_and_replay_is_harmless(self):
        from unittest.mock import patch
        order=start_order(user=self.reader_a,fine_id=self.fine.pk,amount=Decimal(1000),channel="momo",mode="momo_sandbox",request_key=uuid.uuid4())
        data={"amount":1000,"extraData":"","message":"Success","orderId":str(order.pk),"orderInfo":"Library Hub SANDBOX","orderType":"momo_wallet","partnerCode":"PARTNER","payType":"qr","requestId":str(order.request_key),"responseTime":123,"resultCode":0,"transId":456}
        url=reverse("library:momo_ipn")
        with patch("apps.library.payments.momo_keys",return_value=("PARTNER","ACCESS","SECRET")):
            self.assertEqual(self.client.post(url,json.dumps(data),content_type="application/json").status_code,400)
            data["signature"]=signed({**{k:str(v) for k,v in data.items()},"accessKey":"ACCESS"},"SECRET")
            self.assertEqual(self.client.post(url,json.dumps(data|{"amount":1001}),content_type="application/json").status_code,400)
            self.assertEqual(self.client.post(url,json.dumps(data),content_type="application/json").status_code,204)
            self.assertEqual(self.client.post(url,json.dumps(data),content_type="application/json").status_code,204)
        order.refresh_from_db();self.assertEqual(order.state,"success");self.assertEqual(self.fine.balance,4000)
    def test_redirect_parameters_never_confirm_payment(self):
        order=start_order(user=self.reader_a,fine_id=self.fine.pk,amount=Decimal(1000),channel="bank",request_key=uuid.uuid4())
        self.login(self.reader_a);self.client.get(reverse("library:payment_detail",args=[order.pk]),{"resultCode":0,"amount":1000})
        order.refresh_from_db();self.assertEqual(order.state,"pending")
    def test_copy_mutation_and_retirement_guards(self):
        self.login(self.circulation)
        self.assertEqual(self.client.post(reverse("library:copies",args=[self.book_a.pk]),{}).status_code,403)
        self.login(self.cataloger)
        self.assertEqual(self.client.get(reverse("library:copy_edit",args=[self.book_a.pk,self.copy_b.pk])).status_code,404)
        response=self.client.post(reverse("library:copy_edit",args=[self.book_a.pk,self.copy_a.pk]),{"barcode":"CHANGED","is_active":"on","branch":"","shelf_location":"A1","home_loan_override":"unknown"})
        self.copy_a.refresh_from_db();self.assertEqual(self.copy_a.barcode,"TEST-BC-A")
        self.client.post(reverse("library:retire_book",args=[self.book_a.pk]),{"reason":"Ngừng phục vụ"})
        self.book_a.refresh_from_db();self.assertFalse(self.book_a.is_active);self.assertTrue(Book.objects.filter(pk=self.book_a.pk).exists())
    def test_waiver_distinct_approver_and_repeated_approval(self):
        row=FineWaiverRequest.objects.create(fine=self.fine,requested_by=self.circulation,amount=1000,reason="Hoàn cảnh đã xác minh")
        with self.assertRaises(CirculationError): review_waiver(row.pk,self.circulation,"approve","test")
        own=FineWaiverRequest.objects.create(fine=self.fine,requested_by=self.librarian,amount=1000,reason="test")
        with self.assertRaises(CirculationError): review_waiver(own.pk,self.librarian,"approve","test")
        review_waiver(row.pk,self.librarian,"approve","Đồng ý")
        review_waiver(row.pk,self.librarian,"approve","Đồng ý")
        self.fine.refresh_from_db();self.assertEqual(self.fine.balance,3000);self.assertEqual(FinePayment.objects.count(),1)
    def test_role_inspector_and_new_screens_render(self):
        self.login(self.librarian)
        self.assertContains(self.client.get(reverse("library:staff_loan_detail",args=[self.loan_a.pk])),reverse("library:payment_start",args=[self.fine.pk]))
        for user,names in [(self.system_admin,["operations","role_inspector","backup_download","restore_rehearsal"]),(self.librarian,["library:policies","library:waivers","library:reports"]),(self.reader_a,["library:payment_history"])]:
            self.login(user)
            for name in names:self.assertEqual(self.client.get(reverse(name)).status_code,200,name)
        self.login(self.reader_a)
        self.assertContains(self.client.get(reverse("library:payment_start",args=[self.fine.pk])),"Không thu tiền thật")
    def test_system_admin_can_assign_roles_without_superuser_escalation(self):
        self.login(self.system_admin)
        response=self.client.post(reverse("account_detail",args=[self.cataloger.pk]),{"username":self.cataloger.username,"roles":["librarian"],"is_active":"on","reason":"Đổi nhiệm vụ","is_superuser":"on"})
        self.assertEqual(response.status_code,302)
        self.cataloger.refresh_from_db();self.assertFalse(self.cataloger.is_superuser);self.assertTrue(self.cataloger.groups.filter(name="librarian").exists())
        self.client.post(reverse("account_detail",args=[self.system_admin.pk]),{"username":self.system_admin.username,"roles":["librarian"],"reason":"test"})
        self.assertTrue(self.system_admin.groups.filter(name="system_admin").exists())

    def test_vnpay_signature_amount_and_repeated_notification(self):
        from unittest.mock import patch
        from .payments import vnpay_signature, initiate_vnpay
        from django.test import RequestFactory
        order=start_order(user=self.reader_a,fine_id=self.fine.pk,amount=Decimal(1000),channel="bank",mode="vnpay_sandbox",request_key=uuid.uuid4())
        data={"vnp_TmnCode":"TERMINAL","vnp_TxnRef":order.pk.hex,"vnp_Amount":"100000","vnp_OrderInfo":"Library Hub SANDBOX "+order.pk.hex,"vnp_ResponseCode":"00","vnp_TransactionStatus":"00","vnp_TransactionNo":"123456789"}
        url=reverse("library:vnpay_ipn")
        with patch("apps.library.payments.vnpay_keys",return_value=("TERMINAL","SECRET")):
            initiate_vnpay(order,RequestFactory().get("/",HTTP_HOST="localhost"))
            self.assertTrue(order.provider_pay_url.startswith("https://sandbox.vnpayment.vn/"))
            self.assertEqual(self.client.get(url,data).json()["RspCode"],"97")
            data["vnp_SecureHash"]=vnpay_signature(data,"SECRET")
            self.assertEqual(self.client.get(url,data|{"vnp_Amount":"200000"}).json()["RspCode"],"97")
            self.assertEqual(self.client.get(url,data).json()["RspCode"],"00")
            self.assertEqual(self.client.get(url,data).json()["RspCode"],"02")
        order.refresh_from_db();self.assertEqual(order.state,"success");self.assertEqual(self.fine.balance,4000)

    def test_librarian_can_open_vnpay_for_exact_compensation_total(self):
        from unittest.mock import patch
        from urllib.parse import parse_qs, urlsplit
        from .models import DamageCase, LoanEvent
        from .payments import vnpay_signature

        case = DamageCase.objects.create(
            loan=self.loan_a, kind=DamageCase.Kind.MAJOR_DAMAGE, status=DamageCase.Status.APPROVED,
            description="Test", replacement_amount=50000, processing_fee=2000, created_by=self.librarian,
        )
        start = reverse("library:damage_payment_start", args=[case.pk])
        self.login(self.reader_b)
        with patch("apps.library.payments.vnpay_keys", return_value=("TEST", "test-secret")):
            self.assertEqual(self.client.post(start).status_code, 404)
        self.login(self.librarian)
        with patch("apps.library.payments.vnpay_keys", return_value=("TEST", "test-secret")):
            response = self.client.post(start)
            self.assertEqual(response.status_code, 302)
            gateway = urlsplit(response["Location"])
            self.assertEqual(gateway.hostname, "sandbox.vnpayment.vn")
            params = parse_qs(gateway.query)
            self.assertEqual(params["vnp_Amount"], ["5200000"])
            order = PaymentOrder.objects.get(damage_case=case)
            data = {
                "vnp_TmnCode": "TEST", "vnp_TxnRef": order.pk.hex, "vnp_Amount": "5200000",
                "vnp_OrderInfo": params["vnp_OrderInfo"][0], "vnp_ResponseCode": "00",
                "vnp_TransactionStatus": "00", "vnp_TransactionNo": "456",
            }
            data["vnp_SecureHash"] = vnpay_signature(data, "test-secret")
            self.assertEqual(self.client.get(reverse("library:vnpay_ipn"), data).json()["RspCode"], "00")
        confirm = reverse("library:confirm_damage_sandbox", args=[case.pk])
        desk = reverse("library:circulation_desk") + "?tab=loans&operation=fines"
        self.login(self.reader_a)
        self.assertEqual(self.client.post(confirm, {"order_id": order.pk}).status_code, 403)
        self.login(self.librarian)
        self.assertContains(self.client.get(desk), "Xác nhận thanh toán thử")
        for _ in range(2):
            self.assertEqual(self.client.post(confirm, {"order_id": order.pk}).status_code, 302)
        self.assertEqual(LoanEvent.objects.filter(event_type="damage_sandbox_confirmed", reason=order.pk.hex).count(), 1)
        response = self.client.get(desk)
        self.assertContains(response, "Đã xác nhận thanh toán thử tại quầy")
        self.assertNotContains(response, "Xác nhận thanh toán thử</button>")
        case.refresh_from_db()
        self.assertEqual(case.status, DamageCase.Status.APPROVED)
        self.assertIsNone(case.settled_at)

    def test_adjustment_requires_distinct_approval_and_preserves_original_amount(self):
        row=FineWaiverRequest.objects.create(fine=self.fine,kind="adjustment",requested_by=self.circulation,amount=500,reason="Bổ sung khoản tính thiếu có căn cứ")
        review_waiver(row.pk,self.librarian,"approve","Đối chiếu hợp lệ")
        review_waiver(row.pk,self.librarian,"approve","Đối chiếu hợp lệ")
        self.fine.refresh_from_db();self.assertEqual(self.fine.accrued_amount,4000);self.assertEqual(self.fine.balance,4500)
        self.assertEqual(FinePayment.objects.filter(kind="adjustment").count(),1)

    def test_backup_requires_password_and_security_configuration_is_bounded(self):
        from unittest.mock import patch
        self.login(self.system_admin)
        with patch("apps.library.backup.create_backup") as backup:
            response=self.client.post(reverse("backup_download"),{"current_password":"wrong","reason":"test"})
            self.assertEqual(response.status_code,200);backup.assert_not_called()
        self.assertEqual(self.client.post(reverse("operations"),{"name":"Library","notifications_enabled":"on","reminder_days":3,"login_failure_limit":99,"lockout_minutes":0,"session_minutes":999999,"reason":"test"}).status_code,200)
        from apps.core.models import SystemConfiguration
        config=SystemConfiguration.objects.get(pk=1);self.assertEqual(config.login_failure_limit,5);self.assertEqual(config.session_minutes,480)

    def test_report_navigation_defaults_dates_without_required_field_errors(self):
        self.login(self.cataloger)
        response=self.client.get(reverse("library:reports"),{"kind":"inventory"})
        self.assertEqual(response.status_code,200)
        self.assertNotContains(response,"Trường này là bắt buộc")
        self.assertEqual(response.context["row_count"],2)
        self.assertContains(response,'value="'+timezone.localdate().isoformat()+'"')
