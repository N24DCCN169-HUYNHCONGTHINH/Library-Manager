# Triển khai Library Hub lên Render

## Cấu hình dịch vụ

- Python 3; Root Directory: `web`; Free; Singapore.
- Build: `pip install -r requirements-render.txt && python render_build.py`
- Start: `gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 1 --threads 4 --access-logfile -`
- Health Check Path: `/health/`
- `DJANGO_SETTINGS_MODULE=config.render`
- `DJANGO_DEBUG=False`
- `DJANGO_ALLOWED_HOSTS=libraryhub.io.vn`
- `DJANGO_CSRF_TRUSTED_ORIGINS=https://libraryhub.io.vn`
- `DJANGO_SECRET_KEY`: tạo riêng tại Render, không đưa vào Git.

Hostname onrender.com do Render cấp được thêm tự động vào danh sách host và CSRF.
Build chỉ kiểm tra cấu hình và gom static, không chạy migrations, tạo tài khoản hoặc sửa dữ liệu.

## Các bước còn phải hoàn thành trước Deploy

1. Tạo database demo riêng, không sao chép tài khoản, phiên đăng nhập hoặc dữ liệu nhạy cảm từ môi trường đang dùng.
2. Chuẩn bị quyền ứng dụng và chạy migrations riêng. Render chỉ nhận URL pooled của role ứng dụng qua `LIBRARY_APP_DATABASE_URL`; không đưa role owner/migrator vào tiến trình web.
3. Email sử dụng apps.core.email_backend.ResendEmailBackend qua HTTPS. Đặt RESEND_API_KEY và DEFAULT_FROM_EMAIL=Library Hub <no-reply@mail.libraryhub.io.vn>. Không cần EMAIL_HOST với backend này. Hai kiểm thử mô phỏng xác nhận payload, idempotency và xử lý lỗi; việc gửi thật chưa được kiểm chứng.
4. Rà soát mã nguồn, loại trừ env/khóa/backup, rồi đưa bản mới lên GitHub.
5. Cấu hình biến bí mật trên Render và triển khai, kiểm tra onrender.com trước khi trỏ DNS BKNS.
6. Thêm libraryhub.io.vn trong Render; dùng chính bản ghi DNS được Render cung cấp và chờ HTTPS được cấp.

Không lưu SQLite, backup hoặc tệp tải lên quan trọng trên filesystem Render Free vì không bền vững. Upload media cần storage ngoài trước khi sử dụng. Bản Free phù hợp demo và có thời gian ngủ khi không có truy cập.

Nhánh mã hiện tại: feat/day-2-auth-environment. Chọn đúng nhánh trong Render nếu chưa hợp nhất vào main.
