# Bản cập nhật vai trò, nghiệp vụ và vận hành

## Vai trò

Năm nhóm cấp mới: `reader`, `cataloger`, `circulation_staff`, `librarian`, `system_admin`. `library_manager` chỉ được giữ để tương thích bản cũ, không nằm trong lựa chọn cấp mới. Tài khoản admin của chủ dự án được chuyển sang Thủ thư + System Admin theo xác nhận trong cuộc trao đổi.

Nguồn chính sách là `apps/core/roles.py`. `setup_roles` gán đúng bộ quyền, báo lỗi nếu thiếu migration thay vì bỏ qua âm thầm. Không tự gán `is_superuser`, `auth.change_user` hoặc `auth.change_group` cho vai trò thông thường. Gán vai trò qua trang tài khoản chỉ cho System Admin; không tự đổi vai trò/trạng thái, không sửa superuser. Quyền Django hợp từ các nhóm khi kiêm nhiệm.

- Biên mục: đầu sách, ảnh bìa, bản sách, mã vạch và kệ; không giao dịch mượn/trả.
- Lưu thông: quầy, hồ sơ/đăng ký độc giả, tạm đình chỉ thẻ, thu tiền, đề nghị miễn/điều chỉnh; không tự duyệt hoặc mở lại thẻ còn nghĩa vụ.
- Thủ thư: nghiệp vụ, duyệt tài chính có người đề nghị khác, quy định phiên bản và báo cáo tổng hợp. Không quản trị kỹ thuật mặc nhiên.
- System Admin: tài khoản, vai trò, phiên, nhật ký, cấu hình dịch vụ/bảo mật, sao lưu và phục hồi thử. Không tự có quyền giao dịch/kho/tài chính.
- Độc giả: tra cứu; lượt mượn, gia hạn, yêu cầu và thanh toán thử chỉ thuộc dữ liệu của chính mình.

Mỗi URL và thao tác POST kiểm tra quyền server; chức năng dùng ID đối tượng còn lọc theo chủ sở hữu hoặc phạm vi nghiệp vụ. Django Admin tiếp tục yêu cầu MFA, không cho xóa dây chuyền sách/bản sách hoặc sửa trực tiếp sổ giao dịch.

## Các trang mới

- `/staff/access/`: ma trận đọc quyền thật từ Django, chọn vai trò để xem không làm đổi vai trò người xem.
- `/library/staff/reports/`: xem/in (tối đa 100 dòng), Excel/CSV đầy đủ tối đa 50.000 dòng, chọn kỳ. Phân quyền kho, lưu thông, tổng hợp; chống công thức Excel/CSV từ dữ liệu người nhập; không cache công khai; ghi nhật ký xuất.
- `/library/staff/books/<id>/copies/`: bản sách và kệ. Không sửa mã/cơ sở/trạng thái hoạt động khi đang có giao dịch. Không ghi trực tiếp trạng thái mượn qua form kho.
- `/library/staff/books/<id>/retire/`: ngừng sử dụng có lý do và có thể khôi phục; không xóa lịch sử.
- `/library/staff/policies/`: thêm phiên bản quy định; các khoản mượn cũ giữ snapshot.
- `/library/staff/waivers/`: đề nghị miễn/giảm hoặc điều chỉnh tăng có căn cứ; cần người khác có quyền phê duyệt. Hai lần gửi/duyệt cùng khóa không tạo hai bút toán. Không hoàn tiền tự động.
- `/staff/operations/`: thông báo, giới hạn nhập sai 3–5 lần, khóa 15–60 phút, thời hạn phiên mới 30 phút–8 giờ (không vượt giới hạn máy chủ), nhật ký và thu hồi phiên/thiết bị.
- `/staff/operations/backup/`: tải bản sao lưu sau nhập lại mật khẩu và lý do. Tệp chứa dữ liệu nhạy cảm, cần lưu riêng.
- `/staff/operations/restore/`: tải ZIP (20 MB nén, 40 MB giải nén) để phục hồi/đối chiếu trong SQLite cô lập. Không ghi đè PostgreSQL đang phục vụ. Phục hồi chính thức vẫn là thao tác bảo trì của người vận hành, không phải nút phục hồi nóng.

Thông báo định kỳ đọc `SystemConfiguration`; tắt thông báo nghiệp vụ không tắt OTP/bảo mật. Cần đăng ký các lệnh `send_loan_notifications --send` và `send_reservation_notifications` trên lịch tác vụ máy chủ để tự gửi; bản cập nhật không tự đăng ký dịch vụ trả phí hoặc gửi thử thư thật.

## OTP email

Sau khi mật khẩu đúng, tài khoản có email đã xác minh được gửi OTP tự động. Mã băm HMAC, gắn tài khoản + phiên + email, dùng một lần, hết hạn sau 5 phút, tối đa 5 lần nhập sai, 60 giây giữa các lần gửi và 5 lần gửi/giờ. Middleware chặn đi thẳng vào chức năng khi còn chờ OTP, kể cả độc giả. Nhân viên có thể dùng ứng dụng xác thực đã đăng ký. Tài khoản chưa có/ chưa xác minh email tiếp tục theo luồng hiện có, không gửi mã đến email chưa chứng minh sở hữu.

Năm tài khoản thử được tạo chưa gắn email theo yêu cầu chủ dự án, mật khẩu tạm buộc đổi ở lần đầu. Nhân viên phải thiết lập TOTP. Không tắt ngoại lệ thử nghiệm đã được duyệt riêng của tài khoản admin cũ, không áp dụng ngoại lệ đó cho toàn bộ vai trò Admin.

## Thanh toán thử

Sổ `PaymentOrder` tách biệt `FinePayment`; mô phỏng và sandbox không giảm số dư thật, không tạo biên nhận thu thật.

- Vietcombank và MoMo mô phỏng nội bộ dùng được ngay, không có tài khoản/QR nhận tiền thật.
- MoMo Sandbox: endpoint cố định `https://test-payment.momo.vn/v2/gateway/api/create`, chữ ký HMAC-SHA256, callback `/library/payments/momo/ipn/` xác minh chữ ký/đơn/số tiền/merchant trước cập nhật.
- Ngân hàng qua VNPAY Sandbox: endpoint cố định `https://sandbox.vnpayment.vn/paymentv2/vpcpay.html`, HMAC-SHA512, callback `/library/payments/vnpay/ipn/` xác minh chữ ký, merchant, amount x100, mã đơn và trạng thái. Ngân hàng thử do cổng cung cấp, không bảo đảm Vietcombank là lựa chọn thử của nhà cung cấp.
- Return URL chỉ hiển thị; không dùng `resultCode=0` do trình duyệt gửi để ghi nhận thành công. Callback lặp không tạo thêm giao dịch. Giao dịch thử thất bại/hủy/hết hạn không đổi sổ tài chính thật.

Chỉ đặt khóa sandbox của chính dự án trong biến môi trường máy chủ; không commit và không gửi khóa qua chat:

```
LIBRARY_MOMO_SANDBOX_PARTNER_CODE=
LIBRARY_MOMO_SANDBOX_ACCESS_KEY=
LIBRARY_MOMO_SANDBOX_SECRET_KEY=
LIBRARY_VNPAY_SANDBOX_TMN_CODE=
LIBRARY_VNPAY_SANDBOX_HASH_SECRET=
```

Chưa có khóa: dùng mô phỏng nội bộ. Tích hợp nhà cung cấp mới được kiểm thử bằng phản hồi ký giả lập; chưa chứng nhận end-to-end với tài khoản merchant thật. Chưa bật thu tiền thật, không dùng mật khẩu/OTP ngân hàng trên Library Hub.

Tài liệu chính thức:
- https://docs.djangoproject.com/en/5.2/topics/auth/default/#groups
- https://developers.momo.vn/v3/docs/payment/onboarding/integration-process/
- https://developers.momo.vn/v3/docs/payment/api/wallet/onetime/
- https://sandbox.vnpayment.vn/apis/docs/thanh-toan-pay/pay.html
