import json
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile, BadZipFile
from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import permission_required
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.db import transaction
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from .models import AccountSecurityEvent, SystemConfiguration
from .roles import ROLE_CHOICES
from .views import staff_mfa_required
from .lifecycle import record_security_event, revoke_totp_devices

class ConfigurationForm(forms.ModelForm):
    reason=forms.CharField(label="Lý do cập nhật",max_length=300)
    class Meta:
        model=SystemConfiguration
        fields=("name","notifications_enabled","reminder_days","support_email","login_failure_limit","lockout_minutes","session_minutes")
        labels={"name":"Tên hệ thống","notifications_enabled":"Bật gửi thông báo nghiệp vụ","reminder_days":"Nhắc trước hạn (ngày)","support_email":"Email hỗ trợ","login_failure_limit":"Giới hạn nhập sai mật khẩu","lockout_minutes":"Thời gian tạm khóa","session_minutes":"Thời hạn phiên đăng nhập mới"}
    def clean_reminder_days(self):
        value=self.cleaned_data["reminder_days"]
        if not 1<=value<=30: raise forms.ValidationError("Chọn từ 1 đến 30 ngày.")
        return value

class SensitiveOperationForm(forms.Form):
    current_password=forms.CharField(label="Mật khẩu hiện tại của bạn",widget=forms.PasswordInput(attrs={"autocomplete":"current-password"}))
    reason=forms.CharField(label="Lý do thao tác",max_length=300)
    def __init__(self,*args,user,**kwargs): super().__init__(*args,**kwargs);self.user=user
    def clean_current_password(self):
        value=self.cleaned_data["current_password"]
        if not self.user.check_password(value): raise forms.ValidationError("Mật khẩu không đúng.")
        return value

class RestoreForm(SensitiveOperationForm):
    backup=forms.FileField(label="Bản sao lưu .zip để phục hồi thử (tối đa 20 MB)")
    def clean_backup(self):
        upload=self.cleaned_data["backup"]
        if upload.size>20*1024*1024: raise forms.ValidationError("Bản sao lưu vượt 20 MB.")
        try:
            with ZipFile(upload) as archive:
                files=archive.infolist()
                if len(files)>20000 or sum(i.file_size for i in files)>40*1024*1024: raise ValueError()
                if any(i.flag_bits&1 for i in files): raise ValueError()
                if any(Path(i.filename).is_absolute() or ".." in Path(i.filename).parts for i in files): raise ValueError()
                if "manifest.json" not in archive.namelist(): raise ValueError()
        except (BadZipFile,ValueError,OSError): raise forms.ValidationError("Tệp sao lưu không hợp lệ hoặc vượt giới hạn giải nén.")
        upload.seek(0);return upload

@never_cache
@staff_mfa_required
def role_inspector(request):
    role=request.GET.get("role","reader")
    if role not in dict(ROLE_CHOICES): role="reader"
    group=Group.objects.filter(name=role).first()
    granted={f"{p.content_type.app_label}.{p.codename}" for p in group.permissions.select_related("content_type")} if group else set()
    specs=[("Tra cứu sách",None,"Danh mục công khai"),("Thêm / sửa / ngừng sử dụng sách","library.change_book","Không xóa lịch sử giao dịch"),("Quản lý bản sách","library.change_bookcopy","Mã vạch, cơ sở và vị trí kệ"),("Tạo phiếu mượn / trả","library.checkout_loan","Nghiệp vụ tại quầy"),("Quản lý độc giả","core.change_readerprofile","Nhân viên lưu thông chỉ tạm đình chỉ, không tự mở lại thẻ"),("Thu tiền phạt","library.collect_finepayment","Không tự miễn/giảm"),("Duyệt miễn/giảm","library.approve_finepayment","Hai người khác nhau: đề nghị và phê duyệt"),("Báo cáo kho sách","library.view_bookcopy","Excel / CSV"),("Báo cáo mượn/trả","library.view_loan","Excel / CSV"),("Báo cáo tổng hợp","library.view_system_reports","Excel / CSV"),("Quy định mượn/trả","library.add_circulationpolicy","Tạo phiên bản mới"),("Quản lý tài khoản","core.manage_account_lifecycle","Không tự khóa hoặc sửa superuser"),("Gán / thu hồi vai trò","core.assign_account_roles","Không cấp superuser, không sửa vai trò của chính mình"),("Sao lưu / phục hồi thử","core.manage_system_operations","Phục hồi vào DB cô lập, không ghi đè DB đang phục vụ")]
    rows=[{"label":label,"allowed":perm is None or perm in granted,"note":note} for label,perm,note in specs]
    return render(request,"core/role_inspector.html",{"roles":ROLE_CHOICES,"selected_role":role,"rows":rows,"permission_names":sorted(granted)})

@never_cache
@staff_mfa_required
@permission_required("core.manage_system_operations",raise_exception=True)
def operations(request):
    return render_operations(request)


def render_operations(request, *, dashboard=False):
    if not request.user.has_perm("core.manage_system_operations"):
        return HttpResponseForbidden()
    config,_=SystemConfiguration.objects.get_or_create(pk=1)
    form=ConfigurationForm(request.POST if request.method=="POST" else None,instance=config)
    if request.method=="POST" and form.is_valid():
        with transaction.atomic():
            obj=form.save(commit=False);obj.updated_by=request.user;obj.save()
            record_security_event(request.user,AccountSecurityEvent.Kind.SYSTEM_OPERATION,request.user,reason=form.cleaned_data["reason"])
        messages.success(request, "Đã lưu cấu hình hệ thống.")
        return redirect("staff_dashboard" if dashboard else "operations")
    from apps.library.payments import momo_keys, vnpay_keys
    template = "core/admin_dashboard.html" if dashboard else "core/operations.html"
    return render(request,template,{"form":form,"events":AccountSecurityEvent.objects.select_related("subject","actor")[:100],"email_backend":settings.EMAIL_BACKEND.rsplit(".",1)[-1],"momo_ready":all(momo_keys()),"vnpay_ready":all(vnpay_keys()),"users":get_user_model().objects.filter(is_active=True).order_by("username")[:200]})

@never_cache
@staff_mfa_required
@permission_required("core.manage_system_operations",raise_exception=True)
def backup_download(request):
    form=SensitiveOperationForm(request.POST if request.method=="POST" else None,user=request.user)
    if request.method=="POST" and form.is_valid():
        from apps.library.backup import create_backup
        with TemporaryDirectory(prefix="library-backup-") as folder:
            target=Path(folder)/"backup.zip";create_backup(target);data=target.read_bytes()
        record_security_event(request.user,AccountSecurityEvent.Kind.SYSTEM_OPERATION,request.user,reason="Tải sao lưu: "+form.cleaned_data["reason"])
        response=HttpResponse(data,content_type="application/zip");response["Content-Disposition"]='attachment; filename="library-backup-'+timezone.now().strftime("%Y%m%d-%H%M%S")+'.zip"';response["X-Content-Type-Options"]="nosniff";return response
    return render(request,"core/operation_form.html",{"form":form,"heading":"Tải bản sao lưu","description":"Bản sao lưu chứa hồ sơ và dữ liệu bảo mật. Chỉ lưu tại nơi bạn kiểm soát; không chia sẻ công khai.","submit":"Tạo & tải bản sao lưu"})

@never_cache
@staff_mfa_required
@permission_required("core.manage_system_operations",raise_exception=True)
def restore_rehearsal(request):
    form=RestoreForm(request.POST if request.method=="POST" else None,request.FILES or None,user=request.user)
    result=None
    if request.method=="POST" and form.is_valid():
        from apps.library.backup import restore_rehearsal as restore
        try:
            with TemporaryDirectory(prefix="library-restore-") as folder:
                target=Path(folder)/"backup.zip"
                with target.open("wb") as stream:
                    for chunk in form.cleaned_data["backup"].chunks(): stream.write(chunk)
                result=restore(target,Path(folder)/"isolated")
            record_security_event(request.user,AccountSecurityEvent.Kind.SYSTEM_OPERATION,request.user,reason="Phục hồi thử: "+form.cleaned_data["reason"])
        except Exception:
            form.add_error(None,"Không phục hồi được. Cần bản sao lưu hợp lệ, đúng phiên bản ứng dụng. Dữ liệu đang chạy không bị thay đổi.")
    return render(request,"core/operation_form.html",{"form":form,"heading":"Phục hồi thử & kiểm tra bản sao lưu","description":"Tạo cơ sở dữ liệu cô lập, nạp bản sao lưu rồi đối chiếu. Website đang chạy không bị ghi đè. Khôi phục chính thức cần cửa sổ bảo trì và người vận hành thực hiện theo quy trình.","submit":"Phục hồi thử","result":result,"show_official_restore":True})

@never_cache
@staff_mfa_required
@permission_required("core.manage_system_operations",raise_exception=True)
def revoke_sessions(request,user_id):
    subject=get_object_or_404(get_user_model(),pk=user_id)
    form=SensitiveOperationForm(request.POST if request.method=="POST" else None,user=request.user)
    if request.method=="POST" and form.is_valid():
        try: count,sessions=revoke_totp_devices(subject=subject,actor=request.user,reason=form.cleaned_data["reason"],channel="technical_console")
        except PermissionError as exc: form.add_error(None,str(exc))
        else: messages.success(request,f"Đã kết thúc {sessions} phiên và thu hồi {count} thiết bị xác thực.");return redirect("operations")
    return render(request,"core/operation_form.html",{"form":form,"heading":"Thu hồi phiên của "+subject.username,"description":"Kết thúc các phiên đăng nhập và thu hồi thiết bị xác thực. Người dùng cần đăng nhập, xác minh và đăng ký lại thiết bị nếu cần.","submit":"Thu hồi phiên & thiết bị"})
