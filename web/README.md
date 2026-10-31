# Quản lý thư viện — Web MVP

Dự án web mới cho hệ thống quản lý thư viện. Đây là bộ khung để nhóm phát triển tiếp; ứng dụng desktop hiện tại vẫn được giữ riêng tại `D:\QuanLyThuVien_Windows`.

## Công nghệ

- Python 3.14
- Django 6.1
- Django templates + HTML/CSS (không dùng frontend framework riêng trong MVP)
- SQLite để chạy phát triển nhanh; PostgreSQL cho môi trường chia sẻ/triển khai

## Chạy trên Windows

Cài Python 3.14, sau đó mở PowerShell tại thư mục dự án:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
python manage.py migrate
python manage.py runserver
```

Mở http://127.0.0.1:8000/ . Trang `/health/` kiểm tra ứng dụng có phản hồi.

Tạo tài khoản quản trị phát triển bằng `python manage.py createsuperuser`. Máy chủ `runserver` chỉ dành cho phát triển; không dùng làm máy chủ Internet chính thức.

## Tính năng đang có

- Quản lý danh mục sách trong Django Admin tại `/admin/` (thêm, sửa, xóa, tìm kiếm và lọc). Các trường gồm mã, tên, tác giả, thể loại, nhà xuất bản, năm/ấn bản, số bản, ảnh bìa và mô tả.
- Không cho lưu số bản còn lớn hơn tổng số bản.

Sau khi cập nhật mã nguồn, chạy `python manage.py migrate` để tạo bảng sách.

## PostgreSQL

Dự án hỗ trợ cấu hình PostgreSQL qua `.env`. Cài PostgreSQL, tạo database và user riêng, rồi đặt `DB_ENGINE=postgres`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`. Không commit `.env` hoặc mật khẩu lên GitHub.

## GitHub

```powershell
git status
git add .
git commit -m "Create Django web MVP scaffold"
git remote add origin https://github.com/USERNAME/REPOSITORY.git
git push -u origin main
```

Tạo repository GitHub rỗng trước khi thêm `origin` (không chọn tạo README/license trên GitHub vì dự án đã có README).

## Phạm vi 13 ngày

Xem [kế hoạch 13 ngày](docs/plan-13-ngay.md) và [quy ước cộng tác](CONTRIBUTING.md). Ưu tiên đăng nhập/phân quyền, danh mục, độc giả, mượn/trả và chuyển dữ liệu. Thanh toán trực tuyến chỉ làm sandbox nếu các luồng cốt lõi đã ổn định.

## Dữ liệu cũ

Không đưa `library_manager.db`, dữ liệu độc giả, bản sao lưu hoặc mật khẩu thật lên GitHub. Dùng bản sao đã ẩn dữ liệu cá nhân để phát triển và đối chiếu dữ liệu thật chỉ trong môi trường được kiểm soát.
