from io import BytesIO, StringIO
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core import mail
from django.urls import reverse
from django_otp.plugins.otp_totp.models import TOTPDevice
from PIL import Image
from .models import AppearancePreferences, AccountSecurityEvent
from .account_forms import AppearanceForm
User=get_user_model()

@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class AccountAppearanceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("setup_roles", stdout=StringIO())
        cls.manager=User.objects.create_user("manager", email="manager@example.test", password="a-test-password", is_staff=True)
        cls.manager.groups.add(Group.objects.get(name="library_manager"))
        cls.other=User.objects.create_user("worker", email="worker@example.test", password="a-test-password", is_staff=True)
        cls.other.groups.add(Group.objects.get(name="cataloger"))
        cls.reader=User.objects.create_user("regular", password="a-test-password")
        cls.device=TOTPDevice.objects.create(user=cls.manager, name="test", confirmed=True)

    def login_manager(self):
        self.client.force_login(self.manager)
        session=self.client.session;session["otp_device_id"]=self.device.persistent_id;session.save()

    def test_pages_render_and_navigation(self):
        self.login_manager()
        for name,args in [("profile",[]),("appearance_settings",[]),("account_list",[]),("account_detail",[self.other.pk]),("account_add",[])]:
            response=self.client.get(reverse(name,args=args))
            self.assertEqual(response.status_code,200,name)
            self.assertContains(response, 'Tùy chỉnh giao diện')
        self.assertContains(self.client.get(reverse("account_list")),self.reader.username)

    def test_reader_cannot_manage_accounts_and_staff_requires_mfa(self):
        self.client.force_login(self.reader)
        self.assertRedirects(self.client.get(reverse("account_list")), reverse("home"))
        self.client.force_login(self.manager)
        self.assertEqual(self.client.get(reverse("account_list")).status_code,302)
        self.assertEqual(self.client.post(reverse("theme_change"),{"theme":"dark"}).status_code,302)

    def test_manager_cannot_promote_self_or_other_to_manager(self):
        self.login_manager()
        self.client.post(reverse("account_detail",args=[self.manager.pk]),{"username":"manager", "first_name":"Test", "roles":["system_admin"], "reason":"test"})
        self.manager.refresh_from_db()
        self.assertTrue(self.manager.is_active)
        self.assertEqual(list(self.manager.groups.values_list("name",flat=True)),["library_manager"])
        response=self.client.post(reverse("account_detail",args=[self.other.pk]),{"username":"worker", "roles":["library_manager"], "is_active":"on", "reason":"test"})
        self.assertContains(response,"errorlist")
        self.assertFalse(self.other.groups.filter(name="library_manager").exists())

    def test_edit_and_audit_normal_staff(self):
        self.login_manager()
        response=self.client.post(reverse("account_detail",args=[self.other.pk]),{"username":"worker", "first_name":"Updated", "roles":["circulation_staff"], "is_active":"on", "reason":"Đổi công việc"})
        self.assertEqual(response.status_code,302)
        self.other.refresh_from_db();self.assertEqual(self.other.first_name,"Updated")
        self.assertTrue(self.other.groups.filter(name="circulation_staff").exists())
        self.assertTrue(AccountSecurityEvent.objects.filter(subject=self.other,kind="role_changed").exists())

    def test_email_is_pending_and_does_not_change_immediately(self):
        self.login_manager()
        response=self.client.post(reverse("account_detail",args=[self.other.pk]),{"action":"email", "email":"new@example.test", "reason":"Sửa email"})
        self.assertEqual(response.status_code,302)
        self.other.refresh_from_db();self.assertEqual(self.other.email,"worker@example.test")
        self.assertEqual(self.other.email_change_requests.get().pending_email,"new@example.test")
        self.assertEqual(mail.outbox[0].to,["new@example.test"])

    def test_theme_is_private_and_invalid_theme_rejected(self):
        self.client.force_login(self.reader)
        self.assertEqual(self.client.post(reverse("theme_change"),{"theme":"dark"}).status_code,200)
        self.assertEqual(AppearancePreferences.objects.get(user=self.reader).theme,"dark")
        self.assertFalse(AppearancePreferences.objects.filter(user=self.manager).exists())
        self.assertEqual(self.client.post(reverse("theme_change"),{"theme":"bad"}).status_code,400)

    def test_avatar_normalized_and_other_user_cannot_fetch_it(self):
        buffer=BytesIO();Image.new("RGB",(800,500),"red").save(buffer,format="PNG")
        prefs=AppearancePreferences(user=self.reader)
        form=AppearanceForm({"theme":"light","background_color":"#f2f5f4","accent_color":"#087f8c","icon_style":"bold","dashboard_icon":"book"},{"avatar":SimpleUploadedFile("avatar.png",buffer.getvalue(),content_type="image/png")},instance=prefs)
        self.assertTrue(form.is_valid(),form.errors);form.save()
        self.client.force_login(self.reader)
        response=self.client.get(reverse("appearance_image",args=["avatar"]))
        self.assertEqual(response["Content-Type"],"image/jpeg")
        with Image.open(BytesIO(response.content)) as image:self.assertLessEqual(image.width,320)
        self.login_manager();self.assertEqual(self.client.get(reverse("appearance_image",args=["avatar"])).status_code,404)

    def test_svg_and_invalid_colors_rejected(self):
        form=AppearanceForm({"theme":"dark","background_color":"red;bad","accent_color":"#087f8c","icon_style":"thin","dashboard_icon":"grid"},{"avatar":SimpleUploadedFile("x.svg",b"<svg><script>alert(1)</script></svg>")},instance=AppearancePreferences(user=self.reader))
        self.assertFalse(form.is_valid());self.assertIn("avatar",form.errors);self.assertIn("background_color",form.errors)

    def test_other_privileged_account_is_protected(self):
        self.login_manager()
        admin=User.objects.create_user("another-admin",email="another@example.test",is_staff=True)
        admin.groups.add(Group.objects.get(name="system_admin"))
        response=self.client.post(reverse("account_detail",args=[admin.pk]),{"username":"hijack","roles":["cataloger"],"first_name":"changed","reason":"test"})
        admin.refresh_from_db()
        self.assertEqual(admin.username,"another-admin")
        self.assertTrue(admin.is_active)
        self.assertTrue(admin.groups.filter(name="system_admin").exists())
        response=self.client.post(reverse("account_detail",args=[admin.pk]),{"action":"email","email":"hijack@example.test","reason":"test"})
        self.assertEqual(response.status_code,403)

    def test_disable_requires_reason_and_revokes_sessions(self):
        self.login_manager()
        response=self.client.post(reverse("account_detail",args=[self.other.pk]),{"username":"worker","roles":["cataloger"],"reason":"Khóa theo yêu cầu"})
        self.assertEqual(response.status_code,302)
        self.other.refresh_from_db();self.assertFalse(self.other.is_active)
        self.assertTrue(AccountSecurityEvent.objects.filter(subject=self.other,kind="account_disabled").exists())
