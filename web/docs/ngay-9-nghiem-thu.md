# Ngày 9 — Chuyển thử SQLite và đối soát

Ngày cập nhật: 06/11/2026. Phạm vi: công cụ chuyển thử, báo cáo bản ghi lỗi/chờ xử lý và tổng đối soát; không chuyển chính thức toàn bộ dữ liệu cũ vào PostgreSQL.

## Công cụ

Lệnh `migrate_legacy_sqlite` mặc định chỉ đọc SQLite bằng `mode=ro`, tạo snapshot nhất quán bằng SQLite backup, phân loại từng bản ghi và xuất `report.json` + `report.html`. SHA-256 xác nhận tệp nguồn không thay đổi. Không truy vấn DB đích khi chạy mặc định.

Mỗi bảng có tổng nguồn và tổng các nhóm kết quả; hai tổng phải bằng nhau. Tổng lượng sách, bản sẵn sàng, tiền phạt ghi nhận và phân bố trạng thái lượt mượn được báo cáo riêng. Tổng tiền phạt nguồn không được coi là số dư nợ; khoản thu cần đối soát riêng.

Các kết quả:

- `ready`: đầu sách có thông tin hợp lệ và đã ánh xạ rõ loại tài liệu/hình thức mượn.
- `review`: thiếu căn cứ hoặc có lỗi, chờ xử lý; không tự suy diễn mã bản, nhóm độc giả, hạn hoặc nợ.
- `skipped`: tài khoản/mật khẩu cũ không được chuyển; dùng quy trình lời mời của hệ thống mới.
- `imported`: đầu sách đã được chuyển thử vào SQLite cục bộ khi bật tùy chọn ghi.
- `conflict`: mã đã tồn tại ở đích; không ghi đè.

Tùy chọn `--apply-catalog --mapping ... --username ...` chỉ cho phép nhập đầu sách đã đối chiếu vào SQLite cục bộ, bằng tài khoản có quyền thêm sách. Sách được tạo ở trạng thái ngừng hiển thị, không tự sinh bản vật lý hoặc tồn sẵn sàng. Ghi đầu sách trong một giao dịch; không ghi PostgreSQL dùng chung. Không sửa bản ghi trùng mã. Chuyển lại dùng thư mục kết quả mới.

Snapshot giữ toàn bộ bảng nguồn để đối chiếu, bao gồm tài khoản, chứng từ và nhật ký. Báo cáo không đưa tên/địa chỉ/điện thoại độc giả hoặc mật khẩu vào danh sách lỗi. Snapshot chứa dữ liệu gốc và thông tin xác thực cũ; chỉ giữ cục bộ, không commit hoặc gửi công khai.

## Chạy thử trên nguồn hiện tại

Đã đọc `D:\QuanLyThuVien_Windows\library_manager.db`, tạo kết quả tại `D:\Library-Manager\work\day9-review-final-20261106` (thư mục work được Git bỏ qua).

| Dữ liệu | Kết quả |
|---|---|
| Đầu sách | 21, chờ ánh xạ loại tài liệu/hình thức mượn |
| Số lượng bản theo số tổng nguồn | 79; chưa phải 79 bản có mã vạch đã kiểm kê |
| Số sẵn sàng theo nguồn | 79 |
| Độc giả | 6, chờ đối chiếu nhóm, tài khoản và thẻ |
| Lượt mượn | 4; trạng thái nguồn đều Returned |
| Tiền phạt ghi nhận trên lượt | 300.000 đồng; chưa đối trừ khoản thu |
| Khoản thu | 1 bản ghi, được giữ trong snapshot và chờ đối soát |
| Tài khoản cũ | 3, không nhập thông tin đăng nhập |
| Bản ghi tạo trong web hiện hành | 0 |

Các bảng còn lại cũng có tổng và bản ghi chờ xử lý trong báo cáo. Không nhập dữ liệu nguồn vào Neon và không thay đổi file nguồn. Chưa đưa 79 bản tổng hợp thành bản vật lý vì thiếu mã vạch; chưa chuyển hồ sơ/loan/tiền thành dữ liệu nghiệp vụ hoạt động.

## Cách chạy lại

Từ thư mục `D:\Library-Manager\web`, dùng một thư mục kết quả mới:

```powershell
.\.venv\Scripts\python.exe manage.py migrate_legacy_sqlite --source "D:\QuanLyThuVien_Windows\library_manager.db" --output "D:\Library-Manager\work\day9-review-lan2"
```

Lệnh này không ghi vào DB đích, kể cả khi cấu hình ứng dụng đang trỏ tới PostgreSQL. Đóng ứng dụng desktop trước khi tạo bản đối chiếu chính thức. Không đặt thư mục kết quả trong cùng thư mục nguồn và không tái sử dụng thư mục kết quả đã có dữ liệu.

Mẫu ánh xạ ở `legacy/mapping.example.json` chỉ minh họa mã OLD-1; không phải quyết định áp cho mọi sách. Người phụ trách kiểm tra từng đầu sách rồi tạo tệp JSON chứa mã thực và hai thuộc tính material_type/loan_mode. Thêm `--mapping <tệp>` để kiểm tra các đầu sách đã ánh xạ. Tùy chọn ghi thử chỉ dùng khi đã cấu hình đúng SQLite cục bộ, có tài khoản có quyền và đã xem báo cáo.

## Kiểm tra

- 90 kiểm thử toàn dự án đạt, gồm 11 kiểm thử mới cho chuyển thử.
- Bao phủ nguồn/đích không đổi khi dry-run, snapshot giữ bảng/chứng từ, không truy vấn DB đích khi dry-run, không lộ thông tin cá nhân/mật khẩu trong báo cáo, mã trùng, tồn kho sai, ngày sai, tham chiếu mất, tiền âm, mapping chính sách sai, ghi thử sách bất hoạt, chạy lại không ghi đè, quyền nhập, chặn PostgreSQL và hoàn tác khi ghi báo cáo thất bại.
- `manage.py check`, `makemigrations --check --dry-run`, `git diff --check`: đạt. Không cần migration mới.

## Điều kiện còn phải giải quyết trước chuyển chính thức

1. Duyệt ánh xạ loại tài liệu/hình thức mượn, kiểm kê bản vật lý và mã vạch.
2. Xác nhận nhóm độc giả, liên kết tài khoản mới, thời hạn và quy trình xác minh thẻ.
3. Đối chiếu lịch sử loan với từng bản vật lý, chính sách lịch sử và chứng từ tiền; chốt quy tắc cho bảng phụ.
4. Hoàn thiện bộ nạp hồ sơ/loan/tài chính theo các ánh xạ đã duyệt, chạy thử rồi đối soát trước khi ghi vào môi trường dùng chung.
5. Diễn tập khôi phục và có phê duyệt chuyển dữ liệu thật theo quy trình dự án. Ngày 9 hiện cung cấp công cụ đối chiếu và nhập thử danh mục; chưa phải bộ chuyển chính thức đầy đủ mọi nghiệp vụ.
