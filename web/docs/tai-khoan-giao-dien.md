# Tài khoản và giao diện cá nhân

Avatar mở hồ sơ, email, mật khẩu, quản lý tài khoản theo quyền và chuyển Sáng/Tối/Theo thiết bị. Bánh răng mở `/settings/appearance/`: màu nền, màu nhấn, nét biểu tượng, biểu tượng tổng quan, avatar và hình nền riêng.

`/staff/accounts/` yêu cầu nhân viên đã MFA và `auth.view_user`; sửa cần `core.manage_account_lifecycle`, tạo lời mời dùng quyền hiện có. Người quản lý không tự đổi vai trò/trạng thái, không nâng quyền quản trị hoặc sửa tài khoản quản trị khác. Email mới chỉ có hiệu lực sau xác nhận, lịch sử ghi người thao tác và lý do. Không cung cấp mật khẩu rõ.

Ảnh JPG/PNG/WebP được thu gọn sang JPEG và bỏ metadata; giới hạn 2 MB avatar, 5 MB hình nền, 20 triệu pixel. Ảnh lưu trong DB để tồn tại sau khi Render triển khai lại; đường dẫn chỉ trả ảnh của chính người đăng nhập và không cache công khai.

Migration core 0010 phải áp dụng trước triển khai, sao lưu trước/sau. Không thay chính sách nghiệp vụ hay ngoại lệ khóa đăng nhập thử nghiệm.
