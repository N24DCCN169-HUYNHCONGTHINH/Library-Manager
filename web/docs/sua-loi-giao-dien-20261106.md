# Phản hồi giao diện ngày 06/11/2026

Đã xem các ảnh và trích khung hình từ cả hai video được chủ dự án cung cấp. Tài liệu tham khảo menu là ý tưởng điều hướng, không phải đặc tả nghiệp vụ mới.

- Mượn/trả: menu phụ mở từ biểu tượng trên thanh trái, gồm 9 mục theo chức năng hiện có. Các mục trong quầy đổi nội dung tại chỗ và có URL riêng để mở trực tiếp/đi lùi. Gửi biểu mẫu thông thường giữ đúng mục sau khi xử lý hoặc khi có lỗi.
- Hàng chờ: nút kiểm tra giữ chỗ hết hạn nhận JSON và thay bảng tại chỗ; chống bấm lặp trong khi xử lý, không tự tải lại toàn trang hoặc tự gửi lại khi lỗi mạng. Người không dùng JavaScript vẫn được chuyển về đúng mục Đặt trước.
- MFA: đăng nhập nhân viên chuyển ngay sang bước xác minh, sau đó trở về trang đã yêu cầu. Độc giả về cổng cá nhân. Không bỏ qua MFA, không gỡ hay thay thiết bị xác thực. Giao diện ghi rõ mã lấy từ ứng dụng, không phải email; hai nút xác minh và đăng xuất được tách rõ.
- Dashboard: các thẻ kỳ gồm lượt mượn, lượt trả, độc giả mới và đầu sách bổ sung; bảng giao dịch cũng lọc theo kỳ. Quá hạn hiện tại và tổng đầu sách hiện tại nằm trong dải hiện trạng riêng. Không suy ra số độc giả mới từ số lượt mượn hoặc ép các chỉ số độc lập bằng nhau.
- Tra cứu: căn cùng hàng cho ô từ khóa, cơ sở và nút tìm; thông báo gợi ý không đẩy lệch vị trí nhập liệu.
- Nghiệp vụ: chuyển danh sách dài thành bảng, trạng thái có màu, liên kết phiếu chi tiết, khu vực thao tác và thông báo chờ rõ ràng. Tối ưu số truy vấn tính số dư, giữ nguyên công thức tài chính.

Kiểm tra: 157 bài SQLite đạt; 9 bài liên quan điều hướng, MFA, thống kê và quầy đạt trên PostgreSQL QA. Không gửi email hoặc xử lý giữ chỗ thật chỉ để thử giao diện trên website.
