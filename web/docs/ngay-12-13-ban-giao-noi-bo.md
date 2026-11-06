# Bàn giao bản chạy thử nội bộ — ngày 12 và chuẩn bị ngày 13

Ngày: 06/11/2026. Người dùng yêu cầu tự tiếp tục các bước nghiệm thu còn lại thay vì yêu cầu gửi ảnh từng bước. Phạm vi thực hiện là bản nội bộ hiện có; không tự suy diễn xác nhận nghiệp vụ hoặc chấp thuận triển khai công khai.

## Đã xác minh trực tiếp với giao diện

| Kịch bản | Kết quả và bằng chứng |
|---|---|
| Tìm kiếm 60 sách DEMO-HCM | Người dùng đã gửi ảnh xác nhận; điều khiển trình duyệt xác nhận trang 2/3 và chuyển tiếp trang 3/3 vẫn giữ bộ lọc, tổng 60. |
| Thêm/sửa/ngừng sử dụng sách | Các ảnh người dùng đã xác nhận mã TEST-UAT-001, sửa nhan đề và trạng thái ngừng sử dụng, không thấy trong tra cứu công khai. |
| Chặn mã trùng/ISBN sai/năm sai/giá âm | Ảnh người dùng đã xác nhận các lỗi; thông báo trùng mã được sửa thành “Mã danh mục này đã tồn tại.” và đã kiểm tra lại trên trình duyệt. |
| Quý/hiếm chỉ đọc tại chỗ | Ảnh người dùng xác nhận sau khi lưu/mở lại. |
| Quản lý độc giả | Trình duyệt hiển thị 38 hồ sơ (36 mô phỏng + 2 demo cũ); tìm DEMO-HCM-R001 được đúng 1 hồ sơ. |
| Thời hạn thẻ sai | Nhập ngày hết hạn trước ngày bắt đầu bị chặn bằng thông báo tiếng Việt. Trở lại danh sách xác nhận hồ sơ vẫn giữ ngày 06/11/2027, không lưu thử nghiệm sai. |
| Quầy lưu thông | Xác nhận có biểu mẫu mượn/trả/gia hạn/thu phạt, hàng chờ và dữ liệu tổng hợp. Phát hiện và sửa ID trùng của các ô mã vạch/UUID; nhãn trỏ đúng từng biểu mẫu sau tải lại. |

Ảnh chụp mới lưu cục bộ tại `work/uat-final/duplicate-code-vietnamese.png` và `reader-date-validation.png`. Các mẫu thử bị chặn không tạo thêm dữ liệu hợp lệ trong DB đang dùng. Không xóa các sách TEST-UAT mà người dùng đã tự tạo.

## Hoàn thiện và kiểm thử bổ sung

- Việt hóa lỗi trùng mã danh mục/ISBN/mã bạn đọc.
- Menu cho xuống dòng, ô checkbox không còn kéo giãn toàn hàng, textarea vừa chiều rộng, điều chỉnh khoảng cách màn hình hẹp. Chưa xác nhận trên thiết bị điện thoại vật lý.
- Có kiểm thử hành trình liên tục: mượn → gửi lại không trùng → người khác không lấy được bản → đặt trước → trả và giữ chỗ → đúng người nhận → gia hạn → cổng cá nhân/không xem được người khác → trả quá hạn → có nợ chặn mượn → thanh toán không trùng → biên nhận → mượn lại sau trả hết nợ.
- Bộ đầy đủ SQLite: **120 kiểm thử đạt**. Hai kiểm thử bổ sung về hành trình và thông báo trùng mã chạy riêng trên PostgreSQL QA: **2/2 đạt**. Sau tách ID biểu mẫu, chạy lại 54 kiểm thử liên quan: đạt.
- Kết quả PostgreSQL toàn bộ trước bổ sung vẫn giữ: 116 đạt, 2 ca SQLite-only bỏ qua và 8/8 tình huống đồng thời đạt. Không diễn đạt rằng đã chạy lại trọn bộ 120 ca PostgreSQL trong lần này.
- Khởi động lại Waitress/Caddy nội bộ với mã mới, kiểm tra lại TLS, login/static/health 200, origin lạ 403, Host lạ 421 và cookie Secure: đạt.
- Kiểm tra tải nhẹ có giới hạn: 24 HTTP GET qua TLS, 4 luồng trên bản khôi phục riêng; số liệu thực tế lưu `work/uat-final/local-load.json`. Đây chỉ là phép thử cục bộ, không phải chứng nhận tải lớn.
- Không cần migration mới; DB và backup được Git bỏ qua để tránh đưa dữ liệu cục bộ vào nguồn.

## Cách dùng bản bàn giao

- Bản phát triển/dữ liệu dùng thử chính: `http://127.0.0.1:8000/`.
- Bản HTTPS nội bộ, dùng SQLite khôi phục riêng: `https://localhost:9443/`. CA nội bộ chưa cài tin cậy trong Windows; không thay dữ liệu cổng 8000.
- Hướng dẫn dữ liệu/tài khoản: `docs/bo-du-lieu-tphcm.md`.
- Sao lưu/khôi phục/bảo trì: `docs/ngay-10-nghiem-thu.md`.
- Bộ kiểm thử PostgreSQL riêng: `docs/kiem-thu-postgresql-qa.md`.

## Các mục chưa thể chốt thay người dùng

1. Tên miền, máy chủ, DNS và truy cập Internet/4G chưa có; giữ nguyên lựa chọn triển khai nội bộ của ngày 10. Không mở cổng mạng hoặc công khai dữ liệu chỉ để vượt bước nghiệm thu.
2. Không tự tạo căn cứ lịch sử cho hồ sơ/loan/tài chính cũ. Cần dữ liệu ánh xạ và chứng từ thực để chuyển chính thức; báo cáo ngày 9 vẫn giữ các dòng chờ đối chiếu.
3. Chưa đăng ký lịch Windows hoặc lịch máy chủ chạy tự động khi chưa chốt máy thường trực/thời gian/tài khoản vận hành. Script bảo trì và sao lưu đã có; chưa giả định laptop này là máy chủ vận hành.
4. Quy trình mất/hỏng/hoàn tiền, nhắc hạn định kỳ và nghiệp vụ ngoại lệ chưa được chứng nhận hoàn chỉnh. Không dùng việc hành trình thông thường đạt để coi các nghiệp vụ này đã hoàn tất.
5. Chốt ngày 13 cần người dùng duyệt khả năng dùng và chính sách cuối cùng. Bản này đủ để tiếp tục chạy thử nội bộ có kiểm soát, chưa được coi là phê duyệt vận hành thật hoặc hoàn thành mọi yêu cầu dự án.

Không cần người dùng gửi thêm ảnh để hoàn thành các kiểm tra kỹ thuật đã nêu. Nếu phát hiện hành vi sai mới khi sử dụng, ghi thao tác, dữ liệu thử và thông báo lỗi để tái hiện; không gửi mật khẩu hoặc dữ liệu độc giả thật.
