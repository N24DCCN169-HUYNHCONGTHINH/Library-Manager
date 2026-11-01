# Nghiệm thu ngày 2

Ngày cập nhật: 01/11/2026. Phạm vi theo [kế hoạch MVP 13 ngày](plan-13-ngay.md).

| Đầu ra | Trạng thái | Bằng chứng |
|---|---|---|
| Cấu hình môi trường | Hoàn tất | Có mẫu `.env.example`, hướng dẫn Windows và SQLite/PostgreSQL trong [README](../README.md); Django system check đạt. |
| PostgreSQL chia sẻ cho phát triển | Hoàn tất | Nhật ký trong [quy trình PostgreSQL](postgres-shared-development.md) ghi đã áp migrations bằng vai trò migrator, xác minh kết nối pooled bằng vai trò ứng dụng, TLS `verify-full`, không còn migration chờ; CRUD và sequence đã được thử bằng bảng tổng hợp rồi xóa. |
| Đăng nhập và vai trò | Hoàn tất | Có kiểm soát tài khoản bất hoạt, nhóm quyền nghiệp vụ, chặn trang nhân viên theo vai trò, MFA TOTP cho nhân viên/Admin và bắt buộc đổi mật khẩu lần đầu. Bộ kiểm thử bao phủ các luồng này. |

## Kiểm tra cục bộ

Đã chạy với SQLite và cơ sở dữ liệu kiểm thử tạm; không kết nối hoặc ghi vào Neon:

- `python manage.py check` — đạt, không có lỗi.
- `python manage.py makemigrations --check --dry-run` — không có migration thiếu.
- `python manage.py test` — 19 kiểm thử đạt, gồm đăng nhập, tài khoản bất hoạt, giới hạn vai trò, thiết lập/chặn MFA, đổi mật khẩu bắt buộc và nghiệp vụ thư viện.

Trong lúc bổ sung kiểm thử, phát hiện và sửa lỗi thiết bị TOTP mới bị đánh dấu xác nhận trước khi người dùng quét mã. Thiết bị giờ được tạo ở trạng thái chờ xác nhận và chỉ bật sau khi mã TOTP hợp lệ.

Các lệnh tái hiện kiểm tra an toàn được ghi trong mục “Kiểm tra cục bộ an toàn” của README.
