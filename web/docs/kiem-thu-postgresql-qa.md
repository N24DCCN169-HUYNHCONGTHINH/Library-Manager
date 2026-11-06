# Chạy kiểm thử PostgreSQL trên nhánh QA riêng

Ngày cấu hình: 06/11/2026. Nhánh do người dùng tạo: `library-qa-day11`, thuộc dự án `library-manager-dev`.

## Ranh giới dữ liệu

- Kết nối QA chỉ nằm trong `web/.env.qa.local`, được Git bỏ qua. Không thay `.env` hoặc `.env.local` của ứng dụng.
- `config.qa` chỉ cho phép lệnh `manage.py test`, kiểm tra đúng endpoint trực tiếp đã xác nhận và chặn endpoint trùng cấu hình ứng dụng (kể cả tên pooled).
- Bộ test tự tạo cơ sở dữ liệu `test_library_day11` trên nhánh QA, migrate và chạy dữ liệu tổng hợp tại đó, rồi xóa DB kiểm thử sau khi chạy. Không dùng `neondb` làm DB kiểm thử và không flush dữ liệu của nhánh production hoặc dữ liệu sao chép trong `neondb` của QA.
- Vai trò `neondb_owner` trên QA đã được kiểm tra có quyền tạo DB/schema. Không cấp thêm quyền cho `library_app` hoặc `library_migrator` của ứng dụng.
- Email của bộ test dùng backend trong bộ nhớ; không gửi thư thật. Mật khẩu băm nhanh chỉ dùng trong tiến trình test để giảm thời gian kiểm thử, không áp vào cấu hình phục vụ ứng dụng.

## Chạy lại

Từ `D:\Library-Manager\web`:

```powershell
.\.venv\Scripts\python.exe manage.py test --settings=config.qa --noinput --verbosity=2
```

Không dùng cấu hình QA để chạy máy chủ. Host được ghim vào endpoint QA đã xác nhận; nếu xóa/tạo lại nhánh làm endpoint thay đổi, phải kiểm tra và cập nhật ghim trước khi chạy. Lệnh test có quyền xóa/tạo DB kiểm thử được đặt tên riêng trên QA; không đổi tên đó thành DB đang dùng.

Hai kiểm thử nhập danh mục vào SQLite cố ý không áp dụng trên PostgreSQL vì chức năng nhập thử chặn ghi vào PostgreSQL. Chúng phải tiếp tục được chạy trong bộ SQLite, không đổi quy tắc sản phẩm chỉ để làm test PostgreSQL đi qua.

## Điều chỉnh phát hiện khi mở rộng từ SQLite sang PostgreSQL

1. Backup PostgreSQL phải bắt đầu từ giao dịch mới để đặt REPEATABLE READ READ ONLY trước truy vấn đầu tiên. Test sao lưu dùng TransactionTestCase; hàm sao lưu từ chối bị gọi bên trong giao dịch đã mở, thay vì lỗi DB khó hiểu.
2. Khi khôi phục, migrations có thể tạo dữ liệu mặc định không tồn tại trong nguồn. Sau migrate, công cụ làm trống **chỉ SQLite mới được tạo trong thư mục diễn tập**, rồi nạp đúng fixture. Có kiểm thử cố ý thiếu hàng mặc định để bảo đảm không sinh thêm dữ liệu khi khôi phục. DB nguồn không tham gia bước làm trống này.
3. Có 4 kiểm thử bảo vệ cấu hình QA: đúng endpoint/test DB, từ chối dùng để phục vụ app, từ chối endpoint lạ và từ chối endpoint trùng ứng dụng.

## Bằng chứng

Lần chạy cuối: **118 kiểm thử, 116 đạt, 2 bỏ qua vì chỉ áp dụng SQLite**, thời gian 425,094 giây; không còn lỗi. Đủ **8/8 kịch bản đồng thời trên PostgreSQL đạt**. Cùng mã nguồn chạy SQLite: **118/118 đạt** trong 36,527 giây.

Nhật ký lưu tại `work/day11/qa-postgresql-final.log`. Đối chiếu số dòng dữ liệu gốc trên QA trước/sau lưu trong `qa-parent-before.json` và `qa-parent-after.json`: số dòng các bảng tài khoản, đầu sách, bản vật lý, lượt mượn, khoản thu không đổi; xác minh `test_library_day11` không còn trong pg_database sau teardown. Không chỉnh sửa cấu hình hoặc chạy flush trên DB ứng dụng.

Chuỗi kết nối không được ghi vào báo cáo. Vì mật khẩu QA từng xuất hiện trong ảnh gửi vào chat, người dùng nên đổi mật khẩu vai trò trên **đúng nhánh QA**, cập nhật lại `.env.qa.local` và không gửi ảnh/chữ chứa mật khẩu mới. Không đổi mật khẩu hoặc cấu hình vai trò nhánh production khi chỉ đang xử lý QA.
