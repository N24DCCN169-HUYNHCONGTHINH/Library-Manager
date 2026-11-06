# Ngoại lệ khóa đăng nhập khi kiểm thử

Theo yêu cầu trực tiếp của chủ dự án ngày 06/11/2026, chỉ hồ sơ bảo mật của tài khoản admin trên website được bật password_lockout_exempt. Mặc định mọi tài khoản khác là False, bao gồm tài khoản có quyền quản lý hoặc quản trị.

AXES_WHITELIST_CALLABLE kiểm tra cờ theo đúng tài khoản đang hoạt động; không tắt Axes toàn hệ thống. Ngoại lệ không bỏ qua mật khẩu, trạng thái is_active, xác minh hai bước hoặc phân quyền nghiệp vụ. Trường này chỉ đọc trong Django Admin.

Bật/tắt qua lệnh set_login_test_exception với username, actor, mode enable/disable và reason. Người thực hiện cần quyền core.manage_account_lifecycle. Khi bật, chỉ xóa bộ đếm đăng nhập sai của username được chọn; các tài khoản khác cùng IP giữ nguyên bảo vệ. Mỗi thay đổi có sự kiện lockout_exception, người thực hiện và lý do. Ngoại lệ giữ hiệu lực đến khi được tắt rõ ràng.

Kiểm tra: sai mật khẩu 8 lần vẫn không đăng nhập được nhưng không bị khóa; sau đó nhập đúng có thể đăng nhập và vẫn phải xác minh hai bước khi vào trang nhân viên. Một tài khoản quản lý khác cùng IP vẫn bị khóa sau ngưỡng 5 lần. Tắt ngoại lệ khôi phục cơ chế khóa thông thường. Đã kiểm tra hồi quy 151 bài trên SQLite và 3 kịch bản ngoại lệ trên PostgreSQL QA.
