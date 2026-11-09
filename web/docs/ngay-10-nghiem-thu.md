# Ngày 10 — Sao lưu, khôi phục và máy chủ HTTPS thử nghiệm

Ngày cập nhật: 06/11/2026. Theo lựa chọn của người dùng: chưa có tên miền/máy chủ, chuẩn bị và diễn tập trên máy hiện tại trước.

## Đã thực hiện và bằng chứng

| Đầu ra | Kết quả |
|---|---|
| Sao lưu dữ liệu ứng dụng | `backup_library` tạo ZIP có dữ liệu Django, media, manifest số lượng và SHA-256; PostgreSQL dùng giao dịch REPEATABLE READ READ ONLY. |
| Khôi phục diễn tập | `restore_library_rehearsal` chỉ tạo SQLite mới trong thư mục riêng; migrate, nạp dữ liệu, kiểm tra FK và đối chiếu nội dung, số bản ghi. Không thay DB đang chạy. |
| Diễn tập trên dữ liệu hiện có | Backup 514 bản ghi ứng dụng từ PostgreSQL phát triển; khôi phục và đối chiếu thành công. Bằng chứng trong `work/day10/restore-20261106/verification.json`. |
| Máy chủ ứng dụng | Waitress 3.0.2, chỉ nghe 127.0.0.1:9080, tin header HTTPS/IP chỉ từ proxy loopback. |
| HTTPS nội bộ | Caddy 2.11.8, chỉ nghe 127.0.0.1:9443, chứng chỉ localhost từ CA nội bộ; không cài CA vào Windows. Dữ liệu dùng là bản khôi phục SQLite riêng, DEBUG=False, cookie riêng có Secure, không gửi email ra ngoài. |
| Kiểm tra HTTPS | TLS chain xác minh bằng root CA riêng; health/login/static trả 200; POST khác origin trả 403; Host lạ trả 421. Bằng chứng trong `work/day10/https-verification.json`. |
| Cấu hình tương lai | Có settings production, mẫu môi trường và Caddyfile cho tên miền thật; chưa đưa lên Internet. |
| Bảo trì | Có script chạy hết hạn thẻ, cập nhật quá hạn, hết hạn giữ chỗ, gửi thông báo, dọn phiên và backup; khóa chống chạy chồng. Đã thử với bản khôi phục và backend thư bộ nhớ; chưa đăng ký lịch tự động Windows. |

100 kiểm thử toàn dự án đạt, gồm 5 kiểm thử backup/restore mới. Kiểm tra tập trung backup/restore chạy lại đạt sau các điều chỉnh đường dẫn và phiên bản; không cần migration mới. Đã sửa signal tài khoản bỏ qua khi nạp fixture raw để khôi phục không tự tạo hồ sơ bảo mật trùng/sai ID.

`check --deploy` với cấu hình localhost chỉ còn security.W004 vì chủ động không bật HSTS lâu dài trên localhost. Đây không phải kết quả nghiệm thu cấu hình triển khai công khai. HTTPS công khai, DNS, chứng chỉ CA công cộng, SMTP và truy cập từ máy khác còn chờ tên miền/máy chủ.

## Chạy thử HTTPS trên máy này

Phiên thử đang ở `https://localhost:9443/`; bản phát triển `http://127.0.0.1:8000/` giữ nguyên.

Trình duyệt có thể cảnh báo vì CA nội bộ chưa được cài tin cậy. Công cụ kiểm tra tin đúng root CA của phiên thử, không bỏ kiểm tra TLS. Không tự cài CA vào Windows. Nếu muốn dùng trình duyệt với chứng chỉ công cộng, cần tên miền và máy chủ ở bước triển khai sau.

Tài khoản/mật khẩu trong bản khôi phục giống thời điểm backup; phiên đăng nhập cũ không được khôi phục. Các thao tác ở cổng 9443 chỉ đổi dữ liệu bản diễn tập, không đồng bộ ngược về cổng 8000/Neon.

Từ thư mục gốc repo, dừng phiên thử:

```powershell
.\deploy\stop-local-https.ps1
```

Khởi động lại sau khi đã dừng:

```powershell
.\deploy\start-local-https.ps1 -RestoredDatabase "D:\Library-Manager\work\day10\restore-20261106\restored.sqlite3"
.\web\.venv\Scripts\python.exe deploy/verify_local_https.py
```

Script kiểm tra đường dẫn/port, không dừng chương trình đang chiếm port. Script dừng chỉ tác động PID có đúng đường dẫn chương trình và thời điểm khởi động đã ghi. Caddy được tải từ API HTTPS chính thức vào `work/day10/tools/caddy.exe`, SHA-256 `7AA12E0CD12615459AC0D57FF6A06BC7E291A92413ECDAB37E13B6ED89814E4E`; không cài dịch vụ Windows. Script khởi động không tải lại công cụ nếu bạn chuyển dự án sang máy mới.

## Tạo backup mới

Từ `D:\Library-Manager\web`, dùng đường dẫn mới mỗi lần:

```powershell
.\.venv\Scripts\python.exe manage.py backup_library --output "D:\Library-Manager\work\day10\library-backup-lan2.zip"
```

Backup là bản logic dữ liệu ứng dụng, không phải toàn bộ PostgreSQL cluster. Nó gồm tài khoản, mật khẩu băm, khóa MFA, nhóm quyền, dữ liệu nghiệp vụ và media; loại phiên đăng nhập/khóa thử sai để không khôi phục phiên cũ. Content types và permissions được tạo lại bằng migrations, quan hệ dùng natural foreign keys. Không chứa `.env`, khóa cấu hình, mã nguồn, phần mở rộng PostgreSQL hoặc cài đặt máy chủ.

Giữ backup như dữ liệu nhạy cảm: thư mục riêng có quyền truy cập giới hạn, không commit/gửi công khai. ZIP này chưa mã hóa. Trước vận hành thực tế cần bản sao được mã hóa ngoài máy, thời hạn giữ (đề xuất 14 bản ngày và 4 bản tuần), mã nguồn/các phiên bản phụ thuộc tương ứng, và bí mật cấu hình trong kho riêng. Chưa tự sao chép backup ra ngoài máy hoặc tự xóa backup cũ.

Tạm dừng thay đổi schema và ghi media trong lúc backup để có mốc đối chiếu rõ ràng. Sao lưu bổ sung ở cấp PostgreSQL/Neon theo quy trình vận hành khi có hạ tầng; công cụ hiện tại không thay thế các lớp đó.

## Khôi phục vào nơi riêng, không ghi đè

```powershell
.\.venv\Scripts\python.exe manage.py restore_library_rehearsal --backup "D:\Library-Manager\work\day10\library-backup-20261106.zip" --output "D:\Library-Manager\work\day10\restore-lan2"
```

Thư mục phải mới hoặc trống. Công cụ xác minh checksum, chặn đường dẫn thoát thư mục, yêu cầu cùng phiên bản Django; tiến trình con buộc dùng SQLite mới và tắt gửi email, bất kể cấu hình URL PostgreSQL của tiến trình cha. Đối soát lại toàn bộ trường dữ liệu, quan hệ, nhóm quyền và số dòng; báo cáo `verified=true` mới được coi là khôi phục đạt. Giữ cùng mã nguồn/migrations khi diễn tập. Nếu lỗi, xem restore-error.log cục bộ; không đưa log/fixture chứa dữ liệu tài khoản lên nơi công khai.

Muốn thay dữ liệu của máy chủ thật sau sự cố phải có quy trình riêng: ngừng ghi, giữ bản hiện trạng, khôi phục sang DB mới, đối chiếu, thử đăng nhập/nghiệp vụ, rồi chuyển cấu hình kết nối và có đường quay lại. Lệnh diễn tập không thực hiện chuyển đổi này.

## Bảo trì và lịch chạy

`deploy/run-maintenance.ps1 -BackupDirectory <thư_mục>` dùng môi trường cấu hình của tiến trình gọi. Để diễn tập, đặt `DJANGO_SETTINGS_MODULE=config.local_https` và `LIBRARY_HTTPS_DB` đúng bản khôi phục trước khi chạy. Script có thể cập nhật trạng thái/gửi email theo backend đang cấu hình; không chạy nhầm môi trường dùng chung khi chỉ muốn diễn tập.

Chưa đăng ký Scheduled Task tự động. Khi có máy chủ: dùng tài khoản dịch vụ riêng, đặt thư mục làm việc đúng repo, nạp bí mật từ môi trường được bảo vệ, cấu hình Task Scheduler chạy script mỗi ngày và ghi log khi lỗi; tác vụ giữ chỗ/gửi thông báo cần lịch ngắn hơn (ví dụ 5 phút) tách khỏi lịch backup ngày. Kiểm tra báo lỗi và diễn tập restore định kỳ; không dùng quyền admin chỉ để chạy nghiệp vụ.

## Chuẩn bị máy chủ/tên miền sau này

1. Cài phụ thuộc từ requirements, Waitress và Caddy; cấp tên miền trỏ máy chủ, mở 80/443 theo thiết kế mạng.
2. Dùng `deploy/production.env.example` làm danh sách biến, thay toàn bộ giá trị mẫu bằng cấu hình riêng; không commit bí mật.
3. Dùng `config.production`, PostgreSQL app pooled, SMTP thật đã thử; migrations dùng tài khoản migrator/direct theo quy trình dự án. Không dùng backend localhost/email bộ nhớ ngoài môi trường diễn tập.
4. `collectstatic`, kiểm tra deploy, chạy Waitress chỉ loopback, Caddy dùng `deploy/Caddyfile.production` để cấp chứng chỉ công cộng. Không mở cổng backend 9080 ra Internet hoặc tin forwarded headers từ nguồn bất kỳ.
5. Cấu hình HSTS bắt đầu ngắn, chỉ mở rộng/includeSubDomains/preload sau khi xác nhận tất cả hostname liên quan phục vụ HTTPS. Không đánh dấu triển khai công khai hoàn tất khi chưa kiểm tra DNS/chứng chỉ/đăng nhập/MFA/CSRF từ máy khác.

Nguồn kỹ thuật: [Django dumpdata/loaddata](https://docs.djangoproject.com/en/6.0/ref/django-admin/), [Caddy HTTPS](https://caddyserver.com/docs/automatic-https), [skip_install_trust](https://caddyserver.com/docs/caddyfile/options#skip_install_trust), [Waitress](https://docs.pylonsproject.org/projects/waitress/en/stable/).

## Phục hồi chính thức bằng cơ sở dữ liệu mới

1. Kiểm tra bản ZIP bằng **Phục hồi thử** và lưu một bản sao mới của hệ thống đang phục vụ.
2. Tạo PostgreSQL đích trống, dùng URL trực tiếp của tài khoản có quyền chạy migration và nạp dữ liệu. Đặt URL trong biến môi trường riêng `LIBRARY_RESTORE_TARGET_URL`.
3. Trong thư mục `web`, chạy:

   ```powershell
   .\.venv\Scripts\python.exe manage.py prepare_library_restore --backup "D:/sao-luu/library-backup.zip" --output "D:/sao-luu/restore-staging"
   ```

4. Kiểm tra `verification.json` có `verified: true`. Thư mục kết quả chứa dữ liệu cá nhân, chỉ lưu ở nơi được kiểm soát. Nếu có `media/`, chuẩn bị đường dẫn media tương ứng cho phiên bản sẽ chuyển sang.
5. Trong thời gian bảo trì, dừng web và tác vụ ghi dữ liệu. Đổi URL chạy web sang vai trò ứng dụng của đích, đổi URL migration và cấu hình tác vụ định kỳ tương ứng. Kiểm tra đăng nhập, kho sách, phiếu mượn và media trước khi mở lại.
6. Giữ cấu hình và cơ sở dữ liệu cũ để quay lại nếu kiểm tra thất bại. Nếu đã mở hệ thống cho ghi dữ liệu trên đích, cần đối chiếu các giao dịch mới trước khi quay lại.

Lệnh chuẩn bị kiểm tra đích trống và từ chối URL trùng cơ sở dữ liệu hiện tại. Lệnh chỉ nạp dữ liệu vào đích mới. Việc chuyển URL và media do người vận hành thực hiện.
