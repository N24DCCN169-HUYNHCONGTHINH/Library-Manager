"""Sandbox and simulator only. No method in this module posts real FinePayment."""
import hashlib, hmac, json, os, uuid
from datetime import timedelta
from functools import wraps
from urllib.parse import urlparse, urlencode
from urllib.request import Request, urlopen
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction, IntegrityError
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET
from apps.core.views import has_staff_role
from .models import DamageCase, PaymentOrder, Fine, LoanEvent

class PaymentStartForm(forms.Form):
    request_key=forms.UUIDField(initial=uuid.uuid4,widget=forms.HiddenInput)
    channel=forms.ChoiceField(label="Phương thức",choices=[("bank","Ngân hàng / VNPAY"),("momo","MoMo")],widget=forms.RadioSelect)
    amount=forms.DecimalField(label="Số tiền thử (VND)",min_value=1,max_digits=10,decimal_places=0)
    use_bank_sandbox=forms.BooleanField(label="Dùng cổng ngân hàng VNPAY Sandbox đã cấu hình",required=False)
    use_momo_sandbox=forms.BooleanField(label="Dùng cổng MoMo Sandbox đã cấu hình thay cho mô phỏng",required=False)

def payment_access(view):
    @wraps(view)
    @login_required
    def wrapped(request,*args,**kwargs):
        if has_staff_role(request.user) and not request.user.is_verified(): return redirect("otp_verify")
        return view(request,*args,**kwargs)
    return wrapped

def fine_scope(user):
    rows=Fine.objects.select_related("loan__reader__user","loan__copy__book").defer('loan__copy__book__cover_image')
    if has_staff_role(user) and user.has_perm("library.collect_finepayment"): return rows
    return rows.filter(loan__reader__user=user)

def order_scope(user):
    rows=PaymentOrder.objects.select_related("fine__loan__copy__book","requester").defer('fine__loan__copy__book__cover_image')
    if has_staff_role(user) and user.has_perm("library.view_fine"): return rows
    return rows.filter(requester=user)

def momo_keys():
    return tuple(os.getenv(key,"").strip() for key in ("LIBRARY_MOMO_SANDBOX_PARTNER_CODE","LIBRARY_MOMO_SANDBOX_ACCESS_KEY","LIBRARY_MOMO_SANDBOX_SECRET_KEY"))

def signed(data,secret):
    raw="&".join(f"{key}={data[key]}" for key in sorted(data))
    return hmac.new(secret.encode(),raw.encode(),hashlib.sha256).hexdigest()

@transaction.atomic
def start_order(*,user,fine_id,amount,channel,request_key,mode="simulator"):
    fine=get_object_or_404(fine_scope(user).select_for_update(),pk=fine_id)
    existing=PaymentOrder.objects.filter(request_key=request_key).first()
    if existing:
        if (existing.requester_id,existing.fine_id,existing.amount,existing.channel,existing.mode)!=(user.pk,fine.pk,amount,channel,mode):
            raise ValidationError("Mã yêu cầu đã được sử dụng cho giao dịch khác.")
        return existing
    if channel not in {"bank","momo"} or mode not in {"simulator","momo_sandbox","vnpay_sandbox"} or (mode=="momo_sandbox" and channel!="momo") or (mode=="vnpay_sandbox" and channel!="bank"):
        raise ValidationError("Phương thức không hợp lệ.")
    if amount<=0 or amount>fine.balance: raise ValidationError("Số tiền phải lớn hơn 0 và không vượt số dư khoản phạt.")
    now=timezone.now()
    pending=PaymentOrder.objects.filter(requester=user,fine=fine,channel=channel,mode=mode,amount=amount,state="pending",expires_at__gt=now).first()
    if pending: return pending
    return PaymentOrder.objects.create(requester=user,fine=fine,amount=amount,channel=channel,request_key=request_key,mode=mode,expires_at=now+timedelta(minutes=15))

def initiate_momo(order,request):
    partner,access,secret=momo_keys()
    if not all((partner,access,secret)): raise ValidationError("Chưa cấu hình thông tin MoMo Sandbox. Bạn vẫn có thể dùng mô phỏng nội bộ.")
    if order.provider_pay_url: return
    if order.amount<1000: raise ValidationError("Chọn số tiền từ 1.000 VND để thử cổng MoMo Sandbox.")
    payload={"partnerCode":partner,"requestId":str(order.request_key),"orderId":str(order.pk),"amount":str(int(order.amount)),"orderInfo":"Library Hub SANDBOX", "redirectUrl":request.build_absolute_uri(reverse("library:payment_detail",args=[order.pk])),"ipnUrl":request.build_absolute_uri(reverse("library:momo_ipn")),"requestType":"captureWallet","extraData":""}
    payload["signature"]=signed({**payload,"accessKey":access},secret)
    payload["lang"]="vi";payload["autoCapture"]=True
    try:
        req=Request("https://test-payment.momo.vn/v2/gateway/api/create",data=json.dumps(payload).encode(),headers={"Content-Type":"application/json"},method="POST")
        with urlopen(req,timeout=35) as response: result=json.loads(response.read(100000))
        url=result.get("payUrl","")
        parsed=urlparse(url)
        if result.get("resultCode")!=0 or parsed.scheme!="https" or parsed.hostname!="test-payment.momo.vn": raise ValueError()
    except Exception:
        raise ValidationError("Chưa tạo được phiên MoMo Sandbox. Không có khoản phạt thật nào được ghi nhận thanh toán.") from None
    order.provider_pay_url=url;order.save(update_fields=["provider_pay_url"])

@never_cache
@payment_access
def payment_start(request,fine_id):
    fine=get_object_or_404(fine_scope(request.user),pk=fine_id)
    bank_ready = all(vnpay_keys())
    form=PaymentStartForm(request.POST if request.method=="POST" else None,
                          initial={"amount": fine.balance, "channel": "bank", "use_bank_sandbox": bank_ready})
    if request.method=="POST" and form.is_valid():
        try:
            data=form.cleaned_data.copy()
            use_momo=data.pop("use_momo_sandbox");use_bank=data.pop("use_bank_sandbox")
            if use_momo and use_bank: raise ValidationError("Chọn một cổng thử phù hợp với phương thức thanh toán.")
            mode="momo_sandbox" if use_momo else "vnpay_sandbox" if use_bank else "simulator"
            if mode=="vnpay_sandbox" and not all(vnpay_keys()): raise ValidationError("Chưa cấu hình thông tin VNPAY Sandbox; dùng mô phỏng nội bộ trước.")
            if mode=="momo_sandbox" and not all(momo_keys()): raise ValidationError("Chưa có thông tin MoMo Sandbox. Hãy bỏ chọn kết nối cổng để dùng mô phỏng.")
            order=start_order(user=request.user,fine_id=fine.pk,mode=mode,**data)
            if mode=="momo_sandbox": initiate_momo(order,request)
            elif mode=="vnpay_sandbox": initiate_vnpay(order,request)
        except (ValidationError,IntegrityError) as exc:
            form.add_error(None,exc if isinstance(exc,ValidationError) else "Yêu cầu trùng. Hãy mở lại lịch sử giao dịch thử.")
        else: return redirect("library:payment_detail",order_id=order.pk)
    return render(request,"library/payment_start.html",{"fine":fine,"form":form,"momo_ready":all(momo_keys()),"bank_ready":bank_ready})

@never_cache
@payment_access
@require_POST
def confirm_damage_sandbox(request, case_id):
    if not has_staff_role(request.user) or not request.user.has_perm("library.collect_finepayment"):
        return HttpResponseForbidden()
    back = reverse("library:circulation_desk") + "?tab=loans&operation=fines#fines"
    with transaction.atomic():
        case = get_object_or_404(DamageCase.objects.select_for_update(), pk=case_id)
        order = case.payment_orders.filter(
            mode="vnpay_sandbox", state="success", amount=case.compensation_total,
        ).order_by("completed_at", "pk").first()
        if case.status != DamageCase.Status.APPROVED or order is None or str(order.pk) != request.POST.get("order_id"):
            messages.error(request, "Không còn giao dịch thử phù hợp để xác nhận.")
            return redirect(back)
        LoanEvent.objects.get_or_create(
            loan_id=case.loan_id, event_type="damage_sandbox_confirmed", reason=order.pk.hex,
            defaults={"actor": request.user, "details": {"case_id": case.pk, "amount": int(order.amount)}},
        )
    messages.success(request, "Đã xác nhận giao dịch thử tại quầy.")
    return redirect(back)


@never_cache
@payment_access
@require_POST
def damage_payment_start(request, case_id):
    staff = has_staff_role(request.user) and request.user.has_perm("library.collect_finepayment")
    cases = DamageCase.objects.all()
    if staff:
        back = reverse("library:circulation_desk") + "?tab=loans&operation=fines#fines"
    elif request.user.groups.filter(name="reader").exists():
        cases = cases.filter(loan__reader__user=request.user)
        back = reverse("reader_portal") + "#reader-compensation"
    else:
        return HttpResponseForbidden()
    if not all(vnpay_keys()):
        messages.error(request, "Chưa cấu hình VNPAY Sandbox.")
        return redirect(back)
    with transaction.atomic():
        case = get_object_or_404(cases.select_for_update(), pk=case_id)
        if case.status != DamageCase.Status.APPROVED or case.replacement_amount is None or case.compensation_total <= 0:
            messages.error(request, "Hồ sơ chưa có khoản bồi thường đang chờ thu.")
            return redirect(back)
        now = timezone.now()
        order = PaymentOrder.objects.filter(
            damage_case=case, requester=request.user, amount=case.compensation_total,
            state="pending", expires_at__gt=now,
        ).first()
        if order is None:
            order = PaymentOrder.objects.create(
                damage_case=case, requester=request.user, amount=case.compensation_total,
                channel="bank", mode="vnpay_sandbox", request_key=uuid.uuid4(),
                expires_at=now + timedelta(minutes=15),
            )
        initiate_vnpay(order, request)
    return redirect(order.provider_pay_url)


@never_cache
@payment_access
def payment_detail(request,order_id):
    order=get_object_or_404(order_scope(request.user),pk=order_id)
    if order.state=="pending" and order.expires_at<=timezone.now():
        PaymentOrder.objects.filter(pk=order.pk,state="pending").update(state="expired");order.refresh_from_db()
    # Redirect query parameters never prove payment. Only signed IPN updates status.
    return render(request,"library/payment_detail.html",{"order":order,"can_simulate":order.requester_id==request.user.pk and order.mode=="simulator" and order.state=="pending"})

@never_cache
@payment_access
@require_POST
def simulate_payment(request,order_id):
    with transaction.atomic():
        order=get_object_or_404(PaymentOrder.objects.select_for_update(),pk=order_id,requester=request.user,mode="simulator")
        if order.state=="pending":
            if order.expires_at<=timezone.now(): order.state="expired"
            else:
                action=request.POST.get("result")
                if action not in {"success","failed","cancelled"}: return HttpResponseBadRequest()
                order.state=action;order.completed_at=timezone.now();order.provider_transaction="SIM-"+str(order.pk)
            order.save(update_fields=["state","completed_at","provider_transaction"])
    return redirect("library:payment_detail",order_id=order.pk)

@never_cache
@payment_access
def payment_history(request):
    from django.core.paginator import Paginator
    return render(request,"library/payment_history.html",{"page_obj":Paginator(order_scope(request.user),20).get_page(request.GET.get("page"))})

@csrf_exempt
@require_POST
def momo_ipn(request):
    partner,access,secret=momo_keys()
    if not all((partner,access,secret)): return JsonResponse({"message":"Sandbox disabled"},status=503)
    if len(request.body)>16000: return HttpResponse(status=413)
    try:
        data=json.loads(request.body)
        keys=("amount","extraData","message","orderId","orderInfo","orderType","partnerCode","payType","requestId","responseTime","resultCode","transId")
        values={key:str(data[key]) for key in keys};values["accessKey"]=access
        if data["partnerCode"]!=partner or not hmac.compare_digest(signed(values,secret),str(data.get("signature",""))): raise ValueError()
        with transaction.atomic():
            order=PaymentOrder.objects.select_for_update().get(pk=data["orderId"],mode="momo_sandbox",channel="momo")
            if str(order.request_key)!=str(data["requestId"]) or str(int(order.amount))!=str(data["amount"]) or data["orderInfo"]!="Library Hub SANDBOX": raise ValueError()
            if order.state=="pending":
                order.state="success" if str(data["resultCode"])=="0" else "failed"
                order.result_code=str(data["resultCode"])[:30];order.provider_transaction="MOMO-SANDBOX-"+str(data["transId"])[:60];order.completed_at=timezone.now();order.save(update_fields=["state","result_code","provider_transaction","completed_at"])
    except (ValueError,KeyError,TypeError,PaymentOrder.DoesNotExist,ValidationError,IntegrityError):
        return JsonResponse({"message":"Invalid notification"},status=400)
    return HttpResponse(status=204)


def vnpay_keys():
    return tuple(os.getenv(key,"").strip() for key in ("LIBRARY_VNPAY_SANDBOX_TMN_CODE","LIBRARY_VNPAY_SANDBOX_HASH_SECRET"))

def vnpay_signature(data,secret):
    raw=urlencode(sorted((k,str(v)) for k,v in data.items() if v!=""))
    return hmac.new(secret.encode(),raw.encode(),hashlib.sha512).hexdigest()

def initiate_vnpay(order,request):
    merchant,secret=vnpay_keys()
    if not merchant or not secret: raise ValidationError("Chưa cấu hình VNPAY Sandbox.")
    if order.provider_pay_url: return
    data={"vnp_Version":"2.1.0","vnp_Command":"pay","vnp_TmnCode":merchant,"vnp_Amount":str(int(order.amount)*100),"vnp_CurrCode":"VND","vnp_TxnRef":order.pk.hex,"vnp_OrderInfo":"Library Hub SANDBOX "+order.pk.hex,"vnp_OrderType":"other","vnp_Locale":"vn","vnp_ReturnUrl":request.build_absolute_uri(reverse("library:payment_detail",args=[order.pk])),"vnp_IpAddr":request.META.get("REMOTE_ADDR","127.0.0.1"),"vnp_CreateDate":timezone.localtime(order.created_at).strftime("%Y%m%d%H%M%S"),"vnp_ExpireDate":timezone.localtime(order.expires_at).strftime("%Y%m%d%H%M%S")}
    data["vnp_SecureHash"]=vnpay_signature(data,secret)
    order.provider_pay_url="https://sandbox.vnpayment.vn/paymentv2/vpcpay.html?"+urlencode(sorted(data.items()))
    order.save(update_fields=["provider_pay_url"])

@never_cache
@require_GET
def vnpay_ipn(request):
    merchant,secret=vnpay_keys()
    if not merchant or not secret: return JsonResponse({"RspCode":"99","Message":"Sandbox disabled"},status=503)
    if any(len(values)!=1 for _,values in request.GET.lists()) or len(request.META.get("QUERY_STRING",""))>16000:
        return JsonResponse({"RspCode":"97","Message":"Invalid signature"})
    data={key:value for key,value in request.GET.items() if key.startswith("vnp_") and key not in {"vnp_SecureHash","vnp_SecureHashType"}}
    if not hmac.compare_digest(vnpay_signature(data,secret),request.GET.get("vnp_SecureHash","")) or data.get("vnp_TmnCode")!=merchant:
        return JsonResponse({"RspCode":"97","Message":"Invalid signature"})
    if data.get("vnp_TxnRef", "").startswith("TV"):
        from apps.core.memberships import confirm_membership_sandbox
        return confirm_membership_sandbox(data)
    try:
        with transaction.atomic():
            order=PaymentOrder.objects.select_for_update().get(pk=data["vnp_TxnRef"],mode="vnpay_sandbox",channel="bank")
            if str(int(order.amount)*100)!=data.get("vnp_Amount"): return JsonResponse({"RspCode":"04","Message":"Invalid amount"})
            if data.get("vnp_OrderInfo")!="Library Hub SANDBOX "+order.pk.hex: return JsonResponse({"RspCode":"01","Message":"Invalid order"})
            if order.state!="pending": return JsonResponse({"RspCode":"02","Message":"Already confirmed"})
            number=data.get("vnp_TransactionNo","")
            if not number.isdigit() or len(number)>30: raise ValueError()
            order.state="success" if data.get("vnp_ResponseCode")=="00" and data.get("vnp_TransactionStatus")=="00" else "failed"
            order.result_code=data.get("vnp_ResponseCode","")[:30];order.provider_transaction="VNPAY-SANDBOX-"+number;order.completed_at=timezone.now();order.save(update_fields=["state","result_code","provider_transaction","completed_at"])
    except (PaymentOrder.DoesNotExist,KeyError,ValueError,ValidationError,IntegrityError):
        return JsonResponse({"RspCode":"01","Message":"Invalid order"})
    return JsonResponse({"RspCode":"00","Message":"Confirm Success"})
