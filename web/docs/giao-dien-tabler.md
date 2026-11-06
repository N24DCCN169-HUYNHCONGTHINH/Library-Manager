# Giao diện Tabler

Ngày cập nhật: 06/11/2026.

- Tabler Core 1.7.3 được cố định trong package.json/package-lock.json. CSS và JS được lưu tại web/static/vendor/tabler để ứng dụng không phụ thuộc CDN khi sử dụng. Giấy phép MIT đi kèm.
- Bộ màu navy / xanh ngọc, sidebar hiển thị theo quyền, liên kết bỏ qua điều hướng, trạng thái trang hiện tại và focus bàn phím.
- Trang chủ và tổng quan nhân viên; danh mục công khai dạng thẻ; bảng sách/độc giả; biểu mẫu thêm/sửa; quầy mượn/trả; đặt trước/thu phạt; cổng độc giả/chi tiết lượt mượn; đăng nhập/MFA/mật khẩu/email/lời mời dùng cùng giao diện.
- Django Admin giữ nguyên cấu trúc và hành vi quản trị; đồng bộ màu, tên hệ thống và liên kết quay lại nghiệp vụ.
- Bìa sách hiện là hình minh họa thay thế bằng CSS vì mô hình hiện chưa có trường ảnh bìa. Không phải ảnh bìa thật.
- Menu đặt trước và khoản phạt dẫn tới các mục tương ứng trong quầy. Không tạo báo cáo hoặc số liệu không có nguồn dữ liệu.
- Giao diện nhỏ: menu cuộn ngang, thẻ và quầy chuyển về một cột; bảng được cuộn trong vùng riêng. Có kiểu in.

## Xem thử

Mở http://127.0.0.1:8000/ và nhấn Ctrl+F5. Trang nhân viên tại /staff/, danh mục tại /library/catalog/. Bản HTTPS nội bộ dùng dữ liệu phục hồi riêng tại https://localhost:9443/.

## Xác minh

- Toàn bộ 120 kiểm thử SQLite đạt sau khi tích hợp bố cục và tài nguyên.
- 42 kiểm thử tài khoản, độc giả và hành trình nghiệp vụ đạt sau khi thay bảng và hoàn thiện bố cục.
- Biên dịch thành công toàn bộ 29 mẫu HTML.
- Xem trực quan tổng quan, danh mục, quầy, bảng sách, biểu mẫu sửa và đăng nhập trên desktop; quầy hiển thị một cột tại 390 × 844.
- Ảnh chụp kiểm tra lưu trong work/tabler-ui (không đưa vào mã nguồn).

Không thay đổi quy tắc nghiệp vụ, dữ liệu, thông tin đăng nhập hoặc quyền tài khoản trong đợt thay giao diện này. Nghiệm thu cuối cùng về độ thuận tiện cần phản hồi của người sử dụng.

## Tinh chỉnh điều hướng theo ảnh tham khảo

- Thanh trái 88px, nhóm biểu tượng trên nền trắng bo tròn, điểm nhấn xanh lá ngọc; nhãn xuất hiện khi rê chuột hoặc focus bàn phím.
- Thanh trên bo tròn có thương hiệu, điều hướng theo quyền, tìm sách thật, lối tắt theo dõi nghiệp vụ và menu tài khoản. Chuông là lối tắt, không giả lập thông báo chưa đọc.
- Dropdown dùng phần tử details gốc của trình duyệt; chỉ mở một menu tại một thời điểm. Trên màn hình nhỏ, điều hướng trên cuộn ngang.

## Dashboard nghiệp vụ

Bộ lọc ngày/tuần/tháng/năm kèm ngày tham chiếu. Lượt mượn và hồ sơ mới tính trong kỳ; số đầu sách, quá hạn, kho sẵn sàng và hàng chờ tính tại thời điểm xem. Kỳ trước là khoảng liên tiếp có cùng số ngày. Biểu đồ nhóm theo ngày địa phương (theo tháng khi chọn năm), có bảng số liệu chữ. Lịch hạn trả chỉ đếm lượt đang mở trong 7 ngày từ ngày tham chiếu; bảng giao dịch gồm 8 lượt mới nhất toàn hệ thống. Từng khối được kiểm tra quyền phía máy chủ. Dashboard không được lưu cache.

Kiểm tra mới: 3 test về ranh giới ngày, khớp tổng biểu đồ, render trang, phân quyền dữ liệu và bộ lọc/năm nhuận đều đạt trên SQLite.
