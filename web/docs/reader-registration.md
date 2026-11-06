# Đăng ký độc giả công khai

- Trang `/accounts/login/` liên kết tới `/accounts/register/`. Giao diện hai cột, ảnh Thư viện Quốc hội Canada, kính mờ; hỗ trợ Light/Dark/System, bàn phím, màn hình nhỏ và giảm chuyển động. Khách chọn chế độ được lưu trên trình duyệt, không thay đổi thiết lập tài khoản.
- Người dùng nhập họ tên, username, email và mật khẩu theo bộ kiểm tra hiện hành. Không nhận vai trò, quyền nhân viên hay trạng thái kích hoạt từ form công khai.
- Tạo user inactive, chưa gán nhóm hay cấp thẻ. Mật khẩu chỉ lưu bằng bộ băm Django. Chống bẫy bot, CSRF và giới hạn số đăng ký thành công theo nguồn mạng (mặc định 30/giờ; cấu hình REGISTRATION_HOURLY_LIMIT). Không tin X-Forwarded-For do khách gửi.
- Gửi thư xác minh có chữ ký, hạn 24 giờ. GET không xác nhận; chủ hộp thư phải POST xác nhận. Email lỗi thì rollback đăng ký và báo thử lại. Xác minh không tự kích hoạt user.
- System Admin (hoặc superuser) đã qua MFA vào Avatar → Quản lý tài khoản → Duyệt đăng ký độc giả. Thủ thư đơn lẻ, biên mục, lưu thông và độc giả không có quyền duyệt.
- Duyệt yêu cầu email đã xác minh, chọn loại bạn đọc, hạn thẻ và căn cứ duyệt. Tạo mã thẻ ngẫu nhiên, hồ sơ reader đã được người duyệt xác minh, gán duy nhất nhóm reader và kích hoạt. Ghi nhật ký người/thời điểm/quyết định/lý do.
- Từ chối giữ tài khoản inactive, không cấp thẻ. Cả duyệt và từ chối khóa hàng trong transaction, không xử lý trùng. Mở lại tài khoản hoặc nhận lời mời không thay thế quy trình duyệt.
- Người duyệt có thể gửi lại liên kết xác minh hết hạn, tối đa 3 lần/giờ, có nhật ký. Không tự đánh dấu email đã xác minh.
- Độc giả đã được duyệt đăng nhập theo luồng OTP email hiện có. Không tự gửi email thông báo quyết định; quản trị viên theo dõi trạng thái trong danh sách.
- Ảnh: xem `static/library/images/ATTRIBUTION.md`; ghi công và giấy phép hiển thị ở trang đăng nhập/đăng ký.

Kiểm tra: `manage.py test apps.core.test_registration`; PostgreSQL tách biệt: `DJANGO_SETTINGS_MODULE=config.qa` với cơ sở dữ liệu kiểm thử riêng. Không dùng test runner trên cơ sở dữ liệu website.
