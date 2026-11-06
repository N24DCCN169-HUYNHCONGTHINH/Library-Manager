# Tra cứu trực tiếp tại quầy

Trong Mượn sách / Trả sách, khung Tra cứu tại quầy hiển thị cạnh biểu mẫu (xếp dưới trên màn hình nhỏ). Danh sách có 8 mục mỗi trang: độc giả, bản sách, và lượt mượn đang mở. Tìm/lọc cập nhật sau 280ms, phân trang không rời quầy; hỗ trợ bộ lọc bản sẵn sàng/đang mượn.

- Chọn độc giả khi mượn điền mã thẻ. Khi trả, chọn độc giả sẽ lọc danh sách sách đang mượn của người đó.
- Chọn bản sẵn sàng/giữ chỗ điền mã bản cụ thể ở phiếu mượn; bản đang mượn điền vào phiếu trả. Tài liệu chỉ đọc tại chỗ không được chọn mượn mang về.
- Các nút chọn là type=button, không submit. Quota, khóa thẻ, tiền phạt, giữ chỗ, thời hạn và các điều kiện giao dịch vẫn do service hiện có kiểm tra lúc xác nhận. Nhãn thẻ còn hiệu lực không khẳng định đủ mọi điều kiện mượn.
- Chọn/lọc/paging không gây chuyển cảnh ảnh nền. Nội dung người dùng được escape trong template; kết quả chỉ tải từ endpoint nội bộ qua GET. Abort và số thứ tự request ngăn phản hồi cũ đè kết quả mới.
- Endpoint `/library/staff/circulation/browse/` yêu cầu vai trò nhân viên và MFA, quyền view_loan + view_fine, cùng quyền xem riêng cho từng danh sách. Không trả email hoặc mật khẩu; không tải dữ liệu ảnh bìa vào danh sách. Truy vấn phân trang và stable ordering.
- Không có JavaScript vẫn xem/lọc danh sách qua GET; tự điền mã cần JavaScript. Không thay đổi schema hoặc dữ liệu để cài đặt chức năng.

Kiểm thử: `manage.py test apps.library.test_desk_browser apps.library.test_workspace apps.library.test_interactions`; PostgreSQL QA riêng dùng config.qa.
