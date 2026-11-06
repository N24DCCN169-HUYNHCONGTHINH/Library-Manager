# Nghiệm thu ngày 3 — Quản lý sách

Ngày cập nhật: 05/11/2026. Theo kế hoạch 13 ngày, danh mục sách và độc giả nằm trong ngày 3–4. Phân chia thực hiện: ngày 3 quản lý sách; ngày 4 quản lý độc giả và nghiệm thu chung danh mục.

## Đã thực hiện

- Trang `/library/staff/books/`: danh sách cả sách đang sử dụng và ngừng sử dụng, tìm theo nhan đề/tác giả/mã danh mục/ISBN, phân trang 25 đầu sách.
- Thêm và sửa sách bằng giao diện tiếng Việt; ghi người tạo và người cập nhật từ tài khoản đang đăng nhập.
- Kiểm tra trường bắt buộc, mã danh mục hợp lệ/duy nhất, ISBN 10/13 đúng số kiểm tra và chuẩn hóa trước khi kiểm tra trùng. ISBN trống được lưu là NULL để nhiều sách không có ISBN vẫn thêm được.
- Năm xuất bản từ 1 đến năm kế tiếp; giá thay thế không âm. Tài liệu quý/hiếm, báo/tạp chí và luận văn được đặt chỉ đọc tại chỗ khi thêm hoặc sửa.
- Bảo vệ bằng đăng nhập, MFA và quyền Django tương ứng trên từng thao tác, kể cả gửi POST trực tiếp. Vai trò và quyền hiện có được giữ nguyên.
- Liên kết “Quản lý sách” xuất hiện với người có quyền xem sách.

## Kiểm tra

Trên SQLite kiểm thử riêng, không ghi vào PostgreSQL dùng chung:

- `python manage.py test`: 25 kiểm thử đạt, gồm 6 kiểm thử mới về tạo/sửa, dữ liệu sai, ISBN trùng, tài liệu chỉ đọc tại chỗ, tìm kiếm và quyền/MFA.
- `python manage.py check`: đạt.
- `python manage.py makemigrations --check --dry-run`: không cần migration mới.
- `git diff --check`: đạt.

## Kịch bản nghiệm thu giao diện

1. Đăng nhập tài khoản cataloger, librarian hoặc library_manager và xác minh MFA.
2. Mở “Quản lý sách”, thêm một sách không có ISBN; tìm lại bằng mã danh mục.
3. Sửa nhan đề và đánh dấu ngừng sử dụng; sách vẫn xuất hiện trong danh sách nội bộ, không xuất hiện trong tra cứu công khai.
4. Thử mã trùng, nhan đề trống, ISBN sai, năm bằng 0 hoặc giá âm: biểu mẫu phải hiện lỗi và giữ dữ liệu nhập.
5. Tài khoản circulation_staff không được thêm/sửa sách bằng đường dẫn trực tiếp.

Chưa nghiệm thu trực quan trên trình duyệt hoặc triển khai lên máy chủ. Quản lý độc giả bằng giao diện riêng còn ở ngày 4; hiện tiếp tục dùng quy trình quản trị và vòng đời tài khoản đã có.
