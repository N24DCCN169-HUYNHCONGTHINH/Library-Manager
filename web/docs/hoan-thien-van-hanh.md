# Hoàn thiện vận hành sau đối chiếu ngày 1

## Thay đổi đã triển khai trong mã nguồn

- Giá thay thế chỉ hạ trần phạt cho lượt mượn mới khi đã được xác nhận, có nguồn/ngày kiểm tra. Thay đổi giá/nguồn/ngày kiểm tra làm mất xác nhận cũ. Quản lý xác nhận bằng thao tác trên danh mục trong trang quản trị.
- Lượt mượn mới lưu giá đã xác nhận và lịch đóng cửa tại lúc cấp; lịch bổ sung do đóng cửa khẩn cấp vẫn được miễn phạt. Không dựng lại căn cứ giả cho lượt mượn cũ.
- Chạm trần gắn cờ xử lý, giữ lượt mượn mở, lưu sự kiện và hiển thị cảnh báo ở quầy. Không tự chuyển thành mất sách.
- Trả sách phân biệt hao mòn tự nhiên, hỏng nhẹ, hỏng nặng. Hao mòn không tạo hồ sơ bồi thường/hạn chế mượn.
- Tạm ngưng do quá hạn có lưu sự kiện. Quản lý mở lại tại quầy, bắt buộc lý do; từ chối khi còn quá hạn, dư nợ hoặc hồ sơ chưa đóng.
- Nhắc trước hạn ba ngày, ngày đến hạn và mỗi ba ngày quá hạn. Cổng độc giả chỉ thấy thông báo của mình. Phiên bản hạn cũ sau gia hạn không được gửi; gửi lỗi được thử lại và không lưu nội dung lỗi nhạy cảm.
- Đã cấu hình giờ mở cửa 7 ngày theo xác nhận của chủ dự án, có lịch sử trước/sau. Chưa tự tạo lịch nghỉ Lễ/Tết.
- Trang dự tính bồi thường ở `/library/staff/damage/quote/` chỉ dành cho quản lý, áp dụng Phụ lục D; không tự tạo nợ/biên nhận và không thay thế quyết toán hồ sơ mất/hỏng.

## Kiểm tra ngày 06/11/2026

- SQLite: toàn bộ 140 bài đạt; bài bổ sung kiểm tra quyền trang dự tính và không tạo khoản thu đạt riêng.
- PostgreSQL QA tách biệt: lượt chính 135 bài hoàn tất, 2 bài dành cho SQLite được bỏ qua; 11 bài bổ sung cho thay đổi vận hành/biểu phí đều đạt.
- Đã sao lưu dữ liệu công khai trước/sau migration và cấu hình giờ phục vụ vào thư mục cục bộ được bỏ qua bởi Git. Không gửi email hàng loạt trong quá trình cập nhật.

## Chạy nhắc hạn

`python manage.py send_loan_notifications` chỉ tạo thông báo trong tài khoản.

`python manage.py send_loan_notifications --send` tạo thông báo và gửi email. Chỉ bật gửi với môi trường và người nhận đã xác định. Chạy hàng ngày; việc gửi email là cơ chế thử lại, không cam kết chính xác một lần nếu tiến trình chết sau khi nhà cung cấp nhận thư.

Script bảo trì Windows đã gọi bước tạo thông báo. Tham số `-SendLoanEmails` bật gửi nhắc hạn mới. Việc đăng ký lịch tự động vẫn cần máy chạy thường xuyên và lịch được chọn; chạy script thủ công không đồng nghĩa đã có lịch tự động.

## Chưa hoàn tất — không coi là đã nghiệm thu

- Luồng khai mất, dừng/tính lại phạt, khiếu nại, định giá, bồi thường, ghi có, tìm lại trước/sau quyết toán.
- Dòng đảo/hoàn/đối trừ liên kết chứng từ gốc, nộp thừa và bồi thường bằng hiện vật.
- Quản lý toàn bộ thời gian gián đoạn thông báo và tạm dừng đồng hồ giữ chỗ/khiếu nại.
- Audit trước/sau và lý do đồng nhất cho danh mục, bản vật lý, giá, lịch và cấu hình; hồ sơ thiếu căn cứ có người phụ trách/ngày hẹn.
- Dữ liệu thực: ngày nghỉ cụ thể theo thông báo từng năm; nguồn giá và quyết định cho từng hồ sơ; mapping dữ liệu cũ đã đối soát. Giờ phục vụ và khoảng phí đã được chủ dự án xác nhận.
- Đăng ký lịch bảo trì, sao lưu ngoài máy chạy và diễn tập khôi phục; kiểm thử tải, nghiệm thu người dùng.
- Thùng trả vẫn chưa bật: chỉ triển khai khi có điểm nhận, lịch lấy và người phụ trách.

Migration 0006–0007 bổ sung cột/bảng và cho phép sự kiện tự động không gán nhầm nhân viên thực hiện; không thay tiêu đề, mã sách, khoản thu hoặc trạng thái giao dịch cũ. Phải áp dụng migration trước khi khởi động mã mới. Trạng thái website phải được kiểm tra sau triển khai.
