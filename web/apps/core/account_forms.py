from io import BytesIO
from PIL import Image, ImageOps, UnidentifiedImageError
from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from .models import AppearancePreferences

User = get_user_model()
from .roles import ROLE_CHOICES, PRIVILEGED, ALL_ROLES, canonical_roles, can_assign_roles, can_manage_target, protected_user

class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("first_name", "last_name")
        labels = {"first_name": "Tên", "last_name": "Họ và tên đệm"}

class AccountEditForm(ProfileForm):
    roles = forms.MultipleChoiceField(label="Vai trò", choices=ROLE_CHOICES, widget=forms.CheckboxSelectMultiple)
    is_active = forms.BooleanField(label="Cho phép đăng nhập", required=False)
    reason = forms.CharField(label="Lý do chỉnh sửa", max_length=300)
    class Meta(ProfileForm.Meta):
        fields = ("username", "first_name", "last_name")
        labels = {**ProfileForm.Meta.labels, "username": "Tên đăng nhập"}

    def __init__(self, *args, actor, **kwargs):
        super().__init__(*args, **kwargs)
        self.actor = actor
        self.initial["roles"] = list(canonical_roles(self.instance.groups.filter(name__in=ALL_ROLES).values_list("name", flat=True)))
        self.initial["is_active"] = self.instance.is_active
        self.restricted = self.instance.pk == actor.pk or not can_manage_target(actor, self.instance)
        if not can_assign_roles(actor):
            self.fields["roles"].choices = [r for r in ROLE_CHOICES if r[0] not in PRIVILEGED or r[0] in self.initial["roles"]]
        if not can_assign_roles(actor):
            self.fields["roles"].disabled = True
        if self.restricted:
            self.fields["roles"].disabled = True
            self.fields["is_active"].disabled = True
        if not can_manage_target(actor, self.instance):
            for field in ("username", "first_name", "last_name"):
                self.fields[field].disabled = True

    def clean_username(self):
        value = self.cleaned_data["username"]
        if User.objects.filter(username__iexact=value).exclude(pk=self.instance.pk).exists():
            raise ValidationError("Tên đăng nhập đã được sử dụng.")
        return value

    def clean_roles(self):
        roles = set(self.cleaned_data["roles"])
        old = set(self.initial["roles"])
        if not can_assign_roles(self.actor) and roles != old:
            raise ValidationError("Chỉ quản trị viên hệ thống được thay đổi vai trò.")
        if "reader" in roles and not hasattr(self.instance, "reader_profile"):
            raise ValidationError("Hãy tạo hồ sơ độc giả trước khi cấp vai trò Độc giả.")
        if hasattr(self.instance, "reader_profile") and "reader" not in roles:
            raise ValidationError("Giữ vai trò Độc giả để bảo toàn hồ sơ. Có thể đình chỉ thẻ trong Quản lý độc giả.")
        return roles

class ManagedEmailForm(forms.Form):
    email = forms.EmailField(label="Email mới cần xác nhận", max_length=254)
    reason = forms.CharField(label="Lý do đổi email", max_length=300)

class AppearanceForm(forms.ModelForm):
    avatar = forms.FileField(label="Ảnh đại diện (JPG, PNG, WebP; tối đa 2 MB)", required=False)
    background = forms.FileField(label="Hình nền (JPG, PNG, WebP; tối đa 5 MB)", required=False)
    remove_avatar = forms.BooleanField(label="Xóa ảnh đại diện", required=False)
    remove_background = forms.BooleanField(label="Xóa hình nền", required=False)
    class Meta:
        model = AppearancePreferences
        fields = ("theme", "background_color", "accent_color", "icon_style", "dashboard_icon")
        labels = {"theme": "Chế độ hiển thị", "background_color": "Màu nền", "accent_color": "Màu nhấn", "icon_style": "Kiểu biểu tượng", "dashboard_icon": "Biểu tượng tổng quan"}
        widgets = {"background_color": forms.TextInput(attrs={"type": "color"}), "accent_color": forms.TextInput(attrs={"type": "color"})}

    def _image(self, name, limit, size):
        upload = self.cleaned_data.get(name)
        if not upload:
            return None
        if upload.size > limit * 1024 * 1024:
            raise ValidationError(f"Ảnh vượt quá {limit} MB.")
        try:
            with Image.open(upload) as source:
                if source.format not in {"JPEG", "PNG", "WEBP"} or source.width * source.height > 20000000:
                    raise ValueError()
                image = ImageOps.exif_transpose(source)
                image.thumbnail(size)
                image = image.convert("RGB")
                buffer = BytesIO()
                image.save(buffer, format="JPEG", quality=82)
                return buffer.getvalue()
        except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
            raise ValidationError("Ảnh không hợp lệ. Chọn ảnh JPG, PNG hoặc WebP dưới 20 triệu điểm ảnh.")

    def clean_avatar(self):
        return self._image("avatar", 2, (320, 320))

    def clean_background(self):
        return self._image("background", 5, (1600, 1000))

    def save(self, commit=True):
        obj = super().save(commit=False)
        for key, flag in (("avatar", "has_avatar"), ("background", "has_background")):
            image = self.cleaned_data.get(key)
            if self.cleaned_data.get("remove_" + key):
                setattr(obj, key + "_image", b"")
                setattr(obj, flag, False)
            elif image:
                setattr(obj, key + "_image", image)
                setattr(obj, flag, True)
        if commit:
            obj.save()
        return obj
