# PostgreSQL Neon dùng chung cho phát triển

## Môi trường hiện tại

- Neon project: `library-manager-dev`, vùng Singapore (`aws-ap-southeast-1`), nhánh `production`.
- Database: `neondb`. Chỉ dùng dữ liệu giả lập; không nạp hồ sơ bạn đọc thật.
- Mọi bí mật kết nối nằm trong `.env.local` ở thư mục gốc; Git bỏ qua file này.
- Django ưu tiên `LIBRARY_APP_DATABASE_URL` cho ứng dụng và `LIBRARY_MIGRATOR_DATABASE_URL` khi đặt `DJANGO_DB_USE_UNPOOLED=1`. URL Neon mặc định dùng vai trò owner không được dùng cho ứng dụng.

Mỗi máy phát triển cần hai dòng trong `.env.local`, lấy qua kho bí mật của nhóm:

```dotenv
LIBRARY_APP_DATABASE_URL=<pooled connection string for library_app>
LIBRARY_MIGRATOR_DATABASE_URL=<direct connection string for library_migrator>
```

## Vai trò PostgreSQL

Hai vai trò đã được tạo với mật khẩu ngẫu nhiên, không có quyền superuser, tạo database hoặc tạo role:

| Vai trò | Mục đích | Quyền |
|---|---|---|
| `library_app` | Kết nối pooled cho các request của Django | `USAGE` trên schema `public`; đọc, thêm, sửa, xóa dòng trên bảng; dùng sequence. Không có quyền tạo bảng hay sở hữu schema. |
| `library_migrator` | Kết nối trực tiếp để chạy migrations | `CREATE` trên schema `public`; sở hữu các bảng và đối tượng hiện có. Quyền mặc định cấp DML/sequence cho `library_app` trên các đối tượng mới. |

Ứng dụng chỉ dùng vai trò `library_app`. Chỉ người phụ trách tích hợp giữ URL migration; chia sẻ URL qua kho mật khẩu của nhóm, không gửi qua chat hoặc commit vào Git. Không đưa URL owner của Neon vào môi trường ứng dụng. Nếu chạy lại `neon env pull`, kiểm tra `.env.local` và bỏ các URL owner chuẩn do CLI tạo nếu xuất hiện; hai biến `LIBRARY_*_DATABASE_URL` vẫn được Django ưu tiên.

## Cấu hình TLS

Kết nối Neon từ xa dùng `sslmode=verify-full`, kiểm tra cả chứng chỉ và hostname. Django dùng CA bundle Mozilla từ `certifi`; đặt `DB_SSLROOTCERT` chỉ khi môi trường cần một bundle khác. Không hạ chế độ TLS để né lỗi chứng chỉ.

## Quy trình migrations

Người phụ trách tích hợp duy nhất review và chạy migrations. URL trực tiếp dùng cho migrations; ứng dụng chạy bình thường với URL pooled:

```powershell
$env:DJANGO_DB_USE_UNPOOLED='1'
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py migrate --noinput
Remove-Item Env:DJANGO_DB_USE_UNPOOLED
.\.venv\Scripts\python.exe manage.py verify_shared_database
```

`verify_shared_database` xác nhận PostgreSQL, vai trò kết nối, TLS của kết nối client và không còn migrations chờ. Neon pooler có thể chấm dứt TLS trước phiên backend PostgreSQL, vì vậy kiểm tra TLS phía client thay vì dựa vào `pg_stat_ssl` phía máy chủ.

Khi thêm bảng hoặc sequence, người chạy migrations cần dùng `library_migrator` để quyền mặc định tiếp tục cấp quyền DML cho `library_app`. Không sửa schema thủ công. Dùng dữ liệu có hậu tố `TEST` hoặc `SYNTHETIC`.

## Nhật ký xác minh

| Ngày | Trạng thái | Kết quả |
|---|---|---|
| 01/11/2026 | Đã xác minh | Migrations đã áp dụng bằng `library_migrator`; xác minh bằng URL pooled của `library_app` báo PostgreSQL 18.6, TLS `verify-full`, không còn migrations chờ. Thử tạo bảng bằng migrator và thêm/đọc dòng cùng sequence bằng app thành công; bảng thử đã xóa. `/library/catalog/` trả HTTP 200. Working tree chưa commit. |

Không ghi mật khẩu hoặc connection URI đầy đủ vào nhật ký, tài liệu hoặc ảnh chụp màn hình.
