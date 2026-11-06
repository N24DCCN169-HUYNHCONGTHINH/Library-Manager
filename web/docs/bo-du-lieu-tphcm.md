# Bộ dữ liệu TP.HCM — danh mục thực tế và dữ liệu mô phỏng

Ngày lập: 06/11/2026. Theo yêu cầu tạo cả danh mục thư viện thực tế lẫn bộ chạy thử mới, tách khỏi dữ liệu desktop cũ.

## Danh mục thực tế

Nguồn gốc lưu trong `legacy/hcm-libraries.json`; bản xuất ở `work/hcm-dataset-20261106/libraries-real.json` cùng trang tổng hợp `index.html`.

Gồm 6 đơn vị được chọn: Thư viện Khoa học Tổng hợp TP.HCM, Thư viện Trung tâm ĐHQG-HCM, Thư viện ĐH Bách khoa ĐHQG-HCM, Trung tâm TT-TV và Bảo tàng ĐH KHXH&NV ĐHQG-HCM, Thư viện ĐH Sư phạm TP.HCM và Thư viện Phân hiệu ĐH Ngoại thương tại TP.HCM.

Mỗi mục có tên, loại hình, website, địa chỉ nếu đã kiểm chứng, dịch vụ được ghi nhận và URL nguồn chính thức. Địa chỉ hiện hành của Thư viện Trung tâm ĐHQG-HCM và từng cơ sở Thư viện Bách khoa để trống, có ghi chú; không dùng địa chỉ cũ hoặc suy đoán. Một số trang trực tiếp không tải được nên dùng kết quả lập chỉ mục từ cùng website chính thức; thông tin không thay thế kiểm tra trực tiếp trước khi đến thư viện. Đây là danh mục chọn lọc, không phải danh sách đầy đủ mọi thư viện trên địa bàn thành phố.

Các thư viện này độc lập; không nhập chúng thành chi nhánh thật của một hệ thống hoặc cho rằng tài liệu mô phỏng thuộc vốn tài liệu của họ. Không thu thập dữ liệu độc giả, giao dịch hay tồn kho thật của bất kỳ thư viện nào.

## Bộ chạy thử HCM-SYNTHETIC-V1

Đã thêm vào PostgreSQL phát triển bằng các mã riêng `DEMO-HCM-*`, không xóa dữ liệu cũ:

| Nhóm | Số lượng |
|---|---:|
| Cơ sở hoàn toàn mô phỏng | 6 |
| Đầu sách, tác giả hoàn toàn mô phỏng | 60 |
| Bản vật lý có mã vạch | 180 |
| Độc giả giả lập | 36 |
| Lượt mượn | 24 (18 mở, 6 đã trả) |
| Yêu cầu đặt trước | 12 (6 chờ, 6 sẵn sàng nhận) |
| Khoản phạt mô phỏng | 12 |
| Khoản thu mô phỏng | 6 |

Ngày seed lấy ngày Việt Nam, hạn trả đặt 23:59. Có tình huống mượn thường, trong cửa sổ gia hạn, quá hạn có nợ, hàng chờ, đã trả còn nợ một phần và giữ chỗ sẵn sàng nhận. Mỗi cơ sở mô phỏng chỉ tham khảo tên một đơn vị thật trong bản xuất; tên hiện trong ứng dụng luôn là “MÔ PHỎNG TP.HCM — cơ sở …”.

Tài khoản dùng email `example.invalid`, không có mật khẩu dùng được khi tạo. Nhóm chỉ là reader, không có quyền nhân viên. Thẻ xác minh mang phương thức `synthetic_demo`; không coi đây là xác minh người thật. Không gửi lời mời/email khi tạo dữ liệu.

Đã tạo bổ sung 17 chính sách mặc định còn thiếu bằng lệnh cấu hình hiện có; các chính sách đã tồn tại được giữ nguyên. Lượt mượn demo tham chiếu riêng chính sách lịch sử hết hiệu lực hiện tại, không thay chính sách mà quầy chọn cho giao dịch mới.

## Xem và thử

1. Trong “Quản lý sách”, tìm `MÔ PHỎNG` hoặc `DEMO-HCM`. Trang tra cứu lọc theo các cơ sở mô phỏng.
2. Trong “Quản lý độc giả”, tìm `DEMO-HCM`.
3. Thử mượn ở quầy với mã bạn đọc `DEMO-HCM-R001` và mã vạch `DEMO-HCM-B0104-C1`. Độc giả 001 đã có một lượt mượn bình thường, còn hạn mức mặc định.
4. Tài khoản `hcm_demo_02` có sách sắp đến hạn để thử gia hạn; `hcm_demo_03` có sách quá hạn và nợ, nên mượn mới bị chặn. `hcm_demo_04` đang chờ, `hcm_demo_05` đã trả sách và còn khoản phạt một phần, `hcm_demo_06` có sách chờ đến nhận.
5. Đặt mật khẩu tài khoản muốn thử từ PowerShell trong thư mục web:

```powershell
.\.venv\Scripts\python.exe manage.py changepassword hcm_demo_01
```

Sau đó đăng nhập bằng tài khoản đó trong cửa sổ ẩn danh và mở `/reader/`. Bản xuất có danh sách đầy đủ các tên đăng nhập, mã độc giả và tình huống; không có mật khẩu chung được lưu công khai.

## Tạo lại bản xuất hoặc nạp ở môi trường khác

```powershell
.\.venv\Scripts\python.exe manage.py create_hcm_demo_dataset --output "D:\Library-Manager\work\hcm-export-lan2"
```

Mặc định chỉ xuất tệp. Khi cần nạp dữ liệu ở DB mới, thêm `--apply --username <tai_khoan_quan_ly>`. Lệnh kiểm tra quyền và mã trùng; toàn bộ thao tác seed nằm trong một giao dịch. Chạy lại trên DB đã có mã demo sẽ từ chối, không tự xóa, reset tài khoản hoặc sửa các giao dịch đã thử. Thư mục xuất phải mới/trống.

## Kiểm tra

95 kiểm thử toàn dự án đạt; 5 kiểm thử mới bao phủ bản xuất tách dữ liệu thật/mô phỏng, nguồn tham khảo, số lượng, tồn kho khớp lượt mượn, giữ chỗ, số dư nợ, tài khoản không có quyền nhân viên/mật khẩu, chặn nạp trùng, giữ dữ liệu cũ, hoàn tác lỗi và kiểm tra quyền. Không cần migration mới.
