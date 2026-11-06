# Ngày 5–7 — Mượn, trả, gia hạn và đặt trước

Ngày cập nhật: 06/11/2026. Phạm vi: luồng lưu thông của kế hoạch MVP 13 ngày; chưa thay thế nghiệm thu cuối dự án.

## Đã thực hiện

| Nghiệp vụ | Kết quả |
|---|---|
| Mượn | Kiểm tra tài khoản, thẻ đã xác minh/còn hạn, hạn chế, quá hạn, nợ, hạn mức, chính sách và bản vật lý. Bản chỉ đọc tại chỗ, bất hoạt hoặc đã cấp không được cho mượn. |
| Hạn trả | Tính đến 23:59 giờ Việt Nam, dời qua ngày phục vụ khi ngày đến hạn đóng cửa. Chụp chính sách và điều kiện gia hạn vào lượt mượn. |
| Trả | Đóng lượt mượn và cập nhật bản trong cùng giao dịch. Bản bình thường cấp cho hàng chờ; bản bất thường chuyển kiểm tra, tạo hồ sơ tình trạng và hạn chế độc giả. |
| Gia hạn | Tại quầy và cổng độc giả dùng cùng dịch vụ; kiểm tra cửa sổ 48 giờ, số lần, điều kiện tài khoản và hàng chờ. Lưu hạn cũ/mới cùng người thực hiện. |
| Đặt trước | Đặt theo đầu sách khi không còn bản mượn về sẵn sàng; chặn yêu cầu trùng; cấp FIFO theo thời điểm và mã yêu cầu, bỏ người không đủ điều kiện khi phân bổ. |
| Giữ chỗ | Giữ 48 giờ, điều chỉnh qua giờ đóng cửa; hủy/hết hạn chuyển bản cho người kế tiếp. Không cho nhận giữ chỗ đã hết hạn. |
| Thông báo | Yêu cầu sẵn sàng hiển thị trong tài khoản; tạo hàng đợi email, lưu số lần thử, lỗi và thời điểm gửi. Có lệnh gửi/thử lại. |
| Chống gửi lại | Biểu mẫu mượn/trả/gia hạn tại quầy mang UUID thao tác. Gửi lại cùng UUID không tạo lượt/sự kiện thứ hai; UUID dùng cho giao dịch khác bị chặn. |
| Giao diện quầy | Hiển thị lỗi biểu mẫu, thông báo thành công, mã lượt mượn, gia hạn tại quầy, hàng chờ/giữ chỗ và tình trạng email. Kiểm tra quyền từng thao tác tại máy chủ. |

Đã sửa lỗi nợ của lượt đã trả không chặn mượn mới, lỗi quầy làm mất dữ liệu/lỗi nhập, số đếm bản có thể tăng sai do JOIN và trường hợp hạn nhận trước giờ mở cửa bị kéo sang ngày tiếp theo.

## Tính nguyên tử và giới hạn thiết kế

- Dùng từng `BookCopy` làm nguồn tồn kho. Không có phép trừ số lượng tồn kho có thể âm.
- Một hàng khóa dùng chung tuần tự hóa các giao dịch lưu thông trước khi lấy các khóa bản/lượt/độc giả. PostgreSQL khóa hàng; SQLite dùng UPDATE để lấy khóa ghi và thử lại có giới hạn khi bận. Cách này phù hợp MVP nội bộ, chưa tối ưu thông lượng cho thư viện lớn.
- Ràng buộc DB tiếp tục chặn hai lượt mở cho một bản và hai yêu cầu hoạt động của cùng độc giả/đầu sách; bổ sung ràng buộc một bản chỉ được giữ cho một yêu cầu READY.
- Bản chụp số lần/ngày gia hạn cho lượt cũ được điền từ chính sách liên kết tại thời điểm migration; không thể phục hồi phiên bản lịch sử nếu chính sách đó từng bị sửa trước đây.
- Email gửi từ lệnh riêng, không nằm trong giao dịch cấp bản. Email lỗi không xóa thông báo ở tài khoản hoặc kéo dài hạn giữ. Chưa lập lịch tự động các lệnh; đưa vào cấu hình vận hành ngày 10. Nếu dịch vụ thư đã nhận nhưng tiến trình dừng trước khi lưu thời điểm gửi, lần thử lại có thể gửi trùng email.

## Kết quả kiểm tra

- Bộ kiểm thử đầy đủ: 66 kiểm thử trên SQLite tạm, gồm 30 kiểm thử lưu thông mới.
- Có 8 kiểm thử dùng các kết nối/luồng đồng thời: tranh bản cuối, tranh hạn mức cuối, gửi trùng mượn, hai bản trả cấp hai người, gia hạn đồng thời, trả đồng thời, gia hạn tranh với đặt trước và đặt trước trùng.
- Kiểm tra thêm hoàn tác khi ghi sự kiện lỗi; nợ sau trả; thẻ bất hợp lệ; hạn gia hạn; chính sách đã đổi; FIFO; hủy/hết hạn; tài liệu chỉ đọc tại chỗ; email lỗi/thử lại; giao diện quầy giữ lỗi nhập.
- `manage.py check` và `makemigrations --check --dry-run`: đạt.
- Migration `library.0004_circulation_safety` đã áp lên DB phát triển dùng chung bằng vai trò migrator, sau kiểm tra không có READY giữ trùng. Đồng bộ quyền, xác minh lại kết nối pooled của `library_app`, TLS verify-full và không còn migration chờ.
- PostgreSQL: thử luồng mượn/trả/gia hạn/đặt trước/hủy cùng render trang quầy/cổng độc giả/danh mục trong giao dịch hoàn tác; xác nhận dữ liệu tổng hợp không còn sau thử. Kiểm tra hai kết nối riêng xác nhận hàng khóa thực sự chặn giao dịch thứ hai đến khi giao dịch đầu kết thúc.
- Chưa chạy toàn bộ 8 kịch bản đồng thời trên PostgreSQL; kiểm thử đầy đủ đó hiện chạy trên SQLite. Chưa nghiệm thu trực quan hoặc kiểm tra tải lớn.

## Chạy thử giao diện

1. Đăng nhập circulation_staff, librarian hoặc library_manager và xác minh MFA; mở `/library/staff/circulation/` hoặc “Mượn / trả”.
2. Chuẩn bị tài khoản độc giả đã kích hoạt, thẻ đã xác minh/còn hạn; sách có bản vật lý và mã vạch, có chính sách phù hợp. Tạo bản vật lý trong Admin nếu mới chỉ thêm đầu sách. Việc thêm đầu sách không tự tạo bản để cho mượn.
3. Nếu chưa có chính sách mặc định, người phụ trách cấu hình chạy `python manage.py configure_library_defaults --username <tên_nhân_viên>`. Lệnh giữ nguyên chính sách đã có.
4. Nhập mã bạn đọc và mã vạch, xác nhận mượn; kiểm tra mã lượt và hạn trả. Gửi lại cùng biểu mẫu không tạo lượt mới.
5. Thử độc giả thứ hai mượn cùng mã vạch: phải bị từ chối. Thử sách chỉ đọc tại chỗ hoặc thẻ chưa xác minh: phải hiện lý do.
6. Dùng phiên trình duyệt riêng đăng nhập độc giả thứ hai, đặt trước đầu sách đang hết bản sẵn sàng.
7. Trả bản tại quầy, không nhập ghi chú bất thường: yêu cầu đầu hàng chuyển sẵn sàng nhận, bản giữ cho đúng người; độc giả khác không nhận được.
8. Xem cổng độc giả, thử hủy để bản chuyển cho người sau. Quản lý có nút xử lý giữ chỗ hết hạn ở quầy.
9. Gia hạn chỉ thành công trong 48 giờ cuối. Với lượt mới còn hạn 14/30 ngày, bị từ chối là đúng; không sửa ngày dữ liệu dùng chung chỉ để thử. Các tình huống biên đã được kiểm thử tự động.
10. Trả có ghi chú bất thường: bản phải chờ kiểm tra, chưa cấp cho hàng chờ. Xử lý mất/hỏng chuyên sâu và nghiệp vụ ngoại lệ không được nghiệm thu chỉ bằng các kiểm thử này.

## Lệnh vận hành

Từ thư mục `web`, với đúng môi trường phát triển:

```powershell
.\.venv\Scripts\python.exe manage.py expire_reservations
.\.venv\Scripts\python.exe manage.py send_reservation_notifications
.\.venv\Scripts\python.exe manage.py refresh_overdue_loans
```

Lệnh gửi thông báo dùng backend email đang cấu hình và có thể gửi thư thật nếu cấu hình SMTP thật. Dùng dữ liệu tổng hợp và backend thư phát triển để chạy thử. Các lệnh chưa được tự động lên lịch.

Phần tiếp theo theo kế hoạch là ngày 8: kiểm tra và hoàn thiện cổng độc giả, quyền riêng tư và toàn bộ lịch sử/yêu cầu của chính người đăng nhập.
