# Nghiệm thu ngày 4 — Quản lý độc giả

Ngày cập nhật: 05/11/2026. Tiếp nối quản lý sách ngày 3 trong phạm vi danh mục ngày 3–4 của kế hoạch MVP.

## Đã thực hiện

- `/staff/readers/`: danh sách độc giả, tìm theo mã bạn đọc/tên đăng nhập/họ tên/email, lọc trạng thái thẻ và phân trang 25 hồ sơ. Hiển thị riêng trạng thái thẻ, thời hạn, xác minh và khả năng đăng nhập.
- `/staff/readers/add/`: tạo độc giả bằng luồng mời tài khoản có sẵn. Tài khoản chưa kích hoạt, không có mật khẩu dùng được, chỉ thuộc vai trò reader và không có quyền vào Admin. Email mời có hạn 72 giờ; người nhận tự đặt mật khẩu. Xác minh thẻ vẫn thực hiện riêng theo quy trình hiện có.
- `/staff/readers/<id>/edit/`: sửa mã bạn đọc, loại bạn đọc, thời hạn và trạng thái thẻ; bắt buộc lý do. Nhật ký lưu người thao tác, dữ liệu trước/sau và lý do trong cùng giao dịch với cập nhật.
- Biểu mẫu kiểm tra mã hợp lệ/duy nhất, tên đăng nhập và email trùng, ngày bắt đầu/kết thúc, loại độc giả và trạng thái hợp lệ. Lỗi gửi email hoàn tác việc tạo tài khoản/hồ sơ/lời mời.
- Giữ cố định tài khoản liên kết khi sửa. Không cho biểu mẫu sửa quyền, mật khẩu, email hay tự xác minh thẻ. Đổi trạng thái thẻ cần quyền suspend_reader ngoài change_readerprofile; không thay đổi trạng thái đăng nhập.
- Đăng nhập và MFA bắt buộc trên mọi trang. Quyền xem/thêm/sửa kiểm tra tại máy chủ; POST cần CSRF. Không thay đổi ma trận quyền đã chốt.

## Kiểm tra

Đã chạy trên SQLite kiểm thử tạm, không ghi vào PostgreSQL dùng chung:

- `python manage.py test`: 36 kiểm thử đạt, gồm 11 kiểm thử mới cho độc giả và các kiểm thử sách/tài khoản/nghiệp vụ hiện có.
- `python manage.py check`: đạt.
- `python manage.py makemigrations --check --dry-run`: không cần migration mới.
- `git diff --check`: đạt.

Chưa nghiệm thu trực quan trên trình duyệt; chưa triển khai máy chủ hoặc gửi email thật. Không tạo dữ liệu dùng thử trong DB dùng chung.

## Chạy thử

1. Khởi động ứng dụng như README, đăng nhập tài khoản library_manager và hoàn tất MFA.
2. Mở “Quản lý độc giả” hoặc `/staff/readers/`.
3. Chọn “Thêm độc giả”, nhập thông tin tổng hợp và thời hạn thẻ hợp lệ. Sau khi gửi thành công, hồ sơ xuất hiện với thẻ chưa xác minh và đăng nhập chưa bật.
4. Với backend email console, xem liên kết kích hoạt trong terminal chạy máy chủ. Với backend trong bộ nhớ, email không hiện trong terminal và không gửi ra ngoài; chỉ kiểm tra được bằng kiểm thử hoặc cấu hình email phát triển riêng. Không đổi cấu hình thư dùng chung để thử.
5. Mở liên kết mời trong phiên trình duyệt riêng, tự đặt mật khẩu. Việc kích hoạt không tự xác minh thẻ.
6. Quay về tài khoản quản lý, tìm hồ sơ bằng mã/email; sửa thời hạn hoặc trạng thái, nhập lý do. Kiểm tra nhật ký Account security events trong Admin.
7. Thử mã trùng, mã có dấu cách, email trùng và ngày hết hạn trước ngày bắt đầu: phải hiện lỗi.
8. circulation_staff và librarian xem được danh sách; theo quyền mặc định không được thêm/sửa. cataloger, system_admin và reader không xem được danh sách nội bộ.

Phần xác minh thẻ, đổi email, gửi lại/thu hồi lời mời, khóa/mở đăng nhập tiếp tục dùng quy trình quản trị tài khoản đã có. Phần ngày 3–4 đã có triển khai và kiểm thử tự động; cần người dùng chạy kịch bản giao diện trên để nghiệm thu thực tế.
