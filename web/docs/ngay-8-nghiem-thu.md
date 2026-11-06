# Ngày 8 — Cổng độc giả và quyền riêng tư

Ngày cập nhật: 06/11/2026. Phạm vi kế hoạch: độc giả chỉ xem tài khoản, lịch sử và yêu cầu của chính mình.

## Đã thực hiện

- `/reader/` hiển thị tài khoản đang đăng nhập, trạng thái/xác minh/thời hạn thẻ; số lượt đang mượn, số lượt quá hạn, yêu cầu hoạt động và số dư khoản phạt đã ghi nhận.
- Lịch sử mượn có lọc trạng thái và phân trang 20 dòng; bỏ giới hạn cũ chỉ lấy 100 lượt đầu nên truy cập được lịch sử cũ hơn.
- Hiển thị cả yêu cầu đặt trước đang hoạt động và đã hủy/hết hạn/đã nhận/không đủ điều kiện, có phân trang riêng. Vị trí hàng chờ chỉ hiển thị con số, không lộ danh tính người khác. Chỉ yêu cầu hoạt động có nút hủy.
- Khoản phạt phân trang riêng, hiển thị thời điểm tính. Tổng quan tính trên toàn bộ dữ liệu của chính độc giả, không chỉ trang đang xem.
- `/reader/loans/<id>/` hiển thị lượt mượn, ngày mượn/hạn trả/ngày trả, lịch sử gia hạn, khoản phạt và các biên nhận của lượt đó. Không hiển thị tài khoản nhân viên hoặc ghi chú nội bộ của giao dịch thu.
- Mọi truy vấn hồ sơ/lượt/yêu cầu/khoản phạt dựa trên user đăng nhập; không dùng reader_id/user_id từ URL query để chọn người khác. Chi tiết và thao tác nhắm vào lượt/yêu cầu người khác trả 404.
- Các trang riêng tư có Cache-Control private/no-store. Gia hạn, đặt trước, hủy yêu cầu chỉ nhận POST, bảo vệ CSRF và tiếp tục dùng kiểm tra nghiệp vụ ngày 5–7.
- Tải cổng độc giả không tự ghi tiền phạt hoặc đổi trạng thái thẻ. Hiển thị quá hạn theo thời điểm hiện tại; khoản phạt thể hiện số đã ghi nhận và thời điểm tính gần nhất. Tác vụ `refresh_overdue_loans` chịu trách nhiệm cập nhật khoản phát sinh theo hướng dẫn ngày 5–7.
- Tài khoản reader chưa liên kết hồ sơ có thông báo rõ ràng; không trả về hồ sơ người khác. Nhân viên không có vai trò reader được đưa về trang chủ.

## Kiểm tra

- 79 kiểm thử toàn dự án đạt trên SQLite tạm, gồm 13 kiểm thử mới của cổng độc giả.
- Bao phủ phân tách hai độc giả, sửa tham số user/reader trong query, chi tiết và biên nhận, giả mã lượt để gia hạn, giả mã yêu cầu để hủy, CSRF, GET không được thay đổi giao dịch, no-store, hồ sơ chưa liên kết, vai trò nhân viên, lịch sử trên 100 lượt, phân trang độc lập và số dư toàn bộ hồ sơ.
- `manage.py check`, `makemigrations --check --dry-run`, `git diff --check`: đạt. Không cần migration mới cho ngày 8.
- PostgreSQL phát triển: thử tải cổng độc giả và chi tiết lượt của chính mình; kiểm tra no-store và lượt của người khác trả 404. Dữ liệu tổng hợp, phiên và thiết bị OTP thử đều nằm trong giao dịch hoàn tác, không được giữ lại.
- Chưa nghiệm thu trực quan trên trình duyệt/điện thoại. Chưa chạy toàn bộ bộ kiểm thử trên PostgreSQL hoặc kiểm tra tải lớn.

## Chạy thử

1. Mở `/accounts/login/`, đăng nhập tài khoản thuộc nhóm reader đã liên kết hồ sơ. Tài khoản quản lý không tự có vai trò độc giả.
2. Mở `/reader/`, kiểm tra thông tin cá nhân, tổng quan và các danh sách. Thử lọc Đang mượn/Đã trả và chuyển từng trang lịch sử.
3. Nhấn nhan đề trong lịch sử để xem hạn trả, gia hạn và biên nhận. Khoản phạt đang phát sinh có thể chưa được tác vụ cập nhật; luôn đọc mốc “tính đến”.
4. Thử gia hạn khi đủ điều kiện; yêu cầu bị chặn phải có thông báo. Thử hủy đặt trước đang chờ; yêu cầu đã kết thúc vẫn có trong lịch sử và không còn nút hủy.
5. Dùng tài khoản reader thứ hai trong phiên trình duyệt riêng. URL chi tiết lượt của tài khoản thứ nhất phải trả 404. Không dùng hồ sơ thật cho thử nghiệm.
6. Đăng xuất rồi thử truy cập cổng độc giả: phải yêu cầu đăng nhập. Đăng nhập nhân viên chỉ có vai trò nghiệp vụ: không được xem cổng độc giả như một người khác.

Tiếp theo theo kế hoạch: ngày 9 — công cụ chuyển thử dữ liệu SQLite, báo cáo bản ghi lỗi và tổng đối soát.
