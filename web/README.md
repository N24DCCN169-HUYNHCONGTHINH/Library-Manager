# Quản lý thư viện — Web MVP

Dự án web mới cho hệ thống quản lý thư viện. Mã nguồn desktop đang có trong repository được giữ riêng; thư mục backup cũ ngoài repository không phải nguồn làm việc của dự án này.

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

Sau khi chạy migrations, tạo các nhóm quyền bằng `python manage.py setup_roles`, rồi tạo quản trị viên phát triển bằng `python manage.py createsuperuser`. Các nhóm gồm `reader`, `circulation_staff`, `cataloger`, `library_manager` và `system_admin`; `librarian` được giữ để tương thích. Gán đúng nhóm nghiệp vụ trong Django Admin. Chỉ bật `Staff status` riêng cho người cần vào Django Admin. Các nhóm không tự cấp quyền Django Admin.

Hồ sơ bạn đọc được quản lý riêng tại mục “Hồ sơ bạn đọc” trong Django Admin và liên kết một-một với tài khoản. Quản lý thư viện gửi lời mời tại “Bảo mật tài khoản” → “Mời tài khoản”; tài khoản ở trạng thái chờ, mật khẩu chưa được đặt và chỉ hoạt động sau khi người nhận xác nhận liên kết có hạn 72 giờ. Vai trò nhân viên được bật Staff status để vào Admin, nhưng quyền thao tác vẫn giới hạn theo nhóm. Lời mời có thể thu hồi hoặc gửi lại. Với độc giả, lời mời xác minh email nhưng không xác minh danh tính/thẻ: nhân viên phải xác minh riêng trong “Hồ sơ bạn đọc”, thao tác lưu người xác minh và thời điểm. Thẻ hết hạn sẽ tự chặn giao dịch; tác vụ hằng ngày cập nhật thêm trạng thái hết hạn. Không có tự đăng ký công khai.

Đăng nhập tại `/accounts/login/`; đổi mật khẩu tại `/accounts/password_change/`; mọi tài khoản chỉ nhận liên kết khôi phục khi địa chỉ email hiện tại đã được xác minh. Người dùng có thể gửi yêu cầu đổi email tại “Đổi email”; địa chỉ chỉ đổi sau khi xác nhận từ hộp thư mới, và các lần đổi email được ghi vào nhật ký. Nếu email đổi từ trang quản trị, xác minh cũ bị xóa. Tài khoản tạo thủ công từ Django Admin bị buộc đổi mật khẩu ở lần đăng nhập đầu. Khi phát triển, email được in vào terminal. Khi dùng SMTP thật, cấu hình biến `EMAIL_*` trong `.env`. Không dùng email cá nhân/thật trong môi trường dev. Đăng xuất qua nút trên trang bằng POST có CSRF.

Nhân viên và quản trị viên cần đăng nhập tại `/accounts/login/`, sau đó thiết lập mã TOTP bằng ứng dụng xác thực trước khi truy cập dashboard hoặc Django Admin. Khi nhân viên mất thiết bị, quản lý hoặc quản trị được cấp quyền thu hồi tại “Bảo mật tài khoản” → action “Thu hồi thiết bị xác thực OTP”; thao tác ghi người thực hiện, số thiết bị và số phiên đã kết thúc. Có thể dùng lệnh khẩn cấp `python manage.py reset_totp_device <username> --actor <tai_khoan_duoc_uy_quyen>`; lệnh yêu cầu xác nhận tương tác, trừ khi thêm `--yes`. Sau khi thu hồi, mọi phiên của người bị ảnh hưởng bị đăng xuất; họ đăng nhập lại và đăng ký thiết bị mới. Nhật ký bảo mật nằm tại Admin → “Account security events”.

Lập lịch `python manage.py expire_reader_profiles` hằng ngày để ghi nhận thẻ hết hạn. Thao tác khóa/mở đăng nhập nằm trong action của “Bảo mật tài khoản”; mở lại chỉ được phép khi email hiện tại đã xác minh. Tài khoản tạm khóa vẫn giữ lịch sử và không thể đăng nhập.

Mỗi máy cá nhân dùng SQLite nếu không có URL PostgreSQL. Với Neon, lưu hai URL trong `.env.local` ở thư mục gốc (không trong `web/.env`): `LIBRARY_APP_DATABASE_URL` là URL pooled của `library_app`; `LIBRARY_MIGRATOR_DATABASE_URL` là URL trực tiếp của `library_migrator`. Lấy URL qua kho mật khẩu nhóm; không gửi hoặc commit URL. Django bắt buộc xác minh TLS `verify-full` và dùng CA bundle `certifi`.

Chỉ người phụ trách tích hợp áp migrations. Từ thư mục `web`, dùng URL trực tiếp rồi trả về cấu hình pooled để xác minh:

```powershell
$env:DJANGO_DB_USE_UNPOOLED='1'
python manage.py migrate --noinput
Remove-Item Env:DJANGO_DB_USE_UNPOOLED
python manage.py setup_roles
python manage.py verify_shared_database
```

`setup_roles` đồng bộ sáu nhóm và quyền tối thiểu; chạy lại an toàn sau migration hoặc khi cần đồng bộ quyền. Lệnh xác minh kết nối bằng vai trò ứng dụng, TLS phía client và trạng thái migrations; không in mật khẩu. Không nạp dữ liệu bạn đọc thật vào DB phát triển. Xem [quy trình PostgreSQL phát triển dùng chung](docs/postgres-shared-development.md) để biết phân quyền, lưu bí mật và quy trình duy nhất người áp migrations.

Đăng nhập sai được giới hạn theo cặp tên đăng nhập và IP: 5 lần sai trong 15 phút sẽ khóa tạm cặp đó; đăng nhập thành công xóa bộ đếm. Thời gian khóa tự hết sau 15 phút. Nhật ký các thay đổi bảo mật có actor, thời điểm, loại thay đổi và trường lý do; xem trong Django Admin → Account security events.

Ở chế độ `DEBUG=False`, ứng dụng yêu cầu `DJANGO_SECRET_KEY` riêng và không chấp nhận giá trị mẫu. Không bật `DEBUG` ngoài môi trường phát triển. Chạy `python manage.py check --deploy` trước khi triển khai; triển khai thật cần HTTPS và cấu hình bảo mật phù hợp.

Đăng nhập một lần (SSO) chưa bật trong MVP này; cần thống nhất nhà cung cấp tài khoản của trường trước khi tích hợp. MFA TOTP đã được bật bắt buộc cho khu vực nhân viên và Django Admin. Không cấp quyền quản trị cho tài khoản chỉ để vượt qua bước xác minh.

Máy chủ `runserver` chỉ dành cho phát triển; không dùng làm máy chủ Internet chính thức.

## Kiểm tra cục bộ an toàn

Chạy kiểm tra trên SQLite tạm để không kết nối nhầm tới PostgreSQL dùng chung. Trong PowerShell, từ thư mục `web`:

```powershell
$env:DJANGO_DEBUG='True'
$env:DJANGO_SECRET_KEY='test-only-key-do-not-use'
$env:DB_ENGINE='sqlite'
$env:LIBRARY_APP_DATABASE_URL=''
$env:LIBRARY_MIGRATOR_DATABASE_URL=''
$env:DATABASE_URL=''
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
```

`manage.py test` tạo rồi xóa cơ sở dữ liệu kiểm thử riêng. Xóa các biến môi trường ghi đè sau khi kiểm tra hoặc đóng terminal. Không chạy test khi còn URL PostgreSQL trong môi trường tiến trình; Django có thể cố tạo cơ sở dữ liệu kiểm thử trên máy chủ đó.

## PostgreSQL ngoài Neon

Với PostgreSQL không dùng Neon, có thể cấu hình `DB_ENGINE=postgres` cùng `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `DB_SSLMODE` và `DB_SSLROOTCERT` trong `web/.env`. Tài khoản ứng dụng không được là superuser. Không commit `.env` hoặc mật khẩu lên GitHub.

Tài khoản kiểm thử Neon dùng tiền tố `demo_`; thông tin đăng nhập và mã TOTP của tài khoản lưu trong `.env.local` ở thư mục gốc, đã bị Git bỏ qua. Email mẫu dùng miền `.invalid`, không thể nhận thư thật. Để thử mời và đặt lại mật khẩu tự động, dự án dùng backend email trong bộ nhớ; không cấu hình SMTP thật cho các tài khoản này.

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
# Nghiệp vụ danh mục và lưu thông (MVP)

- `/library/catalog/`: tra cứu đầu sách đang hoạt động; tìm theo nhan đề, tác giả, ISBN, mã xếp giá, chủ đề hoặc mã vạch bản sách; lọc theo cơ sở.
- `/library/staff/circulation/`: quầy mượn/trả cho nhân viên có vai trò lưu thông và đã xác minh OTP.
- `/admin/`: quản lý đầu sách, bản sách, bạn đọc, chính sách, giờ mở cửa/ngày nghỉ và hồ sơ giao dịch.
- `/reader/`: bạn đọc xem lượt mượn, đặt trước, trạng thái hàng chờ và khoản phạt của chính mình.

Mỗi bản sách có thể gắn với cơ sở và vị trí kệ. Sau khi áp dụng migration, tạo cơ sở tại Django Admin → “Cơ sở thư viện”, sau đó gán cơ sở/kệ cho từng bản sách. Trang danh mục lọc theo cơ sở, tìm thêm bằng mã vạch bản sách và hiển thị vị trí của các bản sẵn sàng. Bản sách cũ chưa gán cơ sở vẫn được giữ nguyên và hiển thị là chưa gán.

Trong cổng độc giả, thông tin gia hạn nêu điều kiện thời gian (48 giờ cuối), số lần còn lại và trạng thái đặt trước. Nút chỉ hiện khi qua các điều kiện hiển thị cơ bản; backend vẫn kiểm tra lại thẻ, khoản phạt và các hạn chế trước khi lưu. Yêu cầu đặt trước đang chờ hiển thị vị trí hiện tại trong hàng chờ; yêu cầu sẵn sàng nhận hiển thị hạn nhận.

Để dùng tài khoản thử nghiệm Neon, mở thư mục gốc `D:\Library-Manager` trong VS Code, mở `.env.local` (nằm ngoài `web`) và tra các biến `LIBRARY_TEST_*_USERNAME` cùng `LIBRARY_TEST_*_PASSWORD`. Không dán các giá trị này vào Git, chat hoặc ảnh chụp. TOTP của quản lý và thủ thư thử nghiệm nằm trong các biến `LIBRARY_TEST_*_TOTP_SECRET`; nhập vào ứng dụng xác thực như một khóa thiết lập thủ công. Các tài khoản đều dùng email `.invalid`, nên không nhận thư thật. Luồng mời và khôi phục đã được kiểm tra bằng bộ nhớ email giả lập.

Kiểm tra trên SQLite cục bộ, không thay đổi DB Neon:

```powershell
$env:LIBRARY_APP_DATABASE_URL=''
$env:LIBRARY_MIGRATOR_DATABASE_URL=''
$env:DATABASE_URL=''
$env:DB_ENGINE='sqlite'
python manage.py test apps.library.tests
```

Sau khi migrate, cấu hình chính sách mặc định theo Ngày 1 (lệnh chỉ tạo bản ghi còn thiếu; không ghi đè cấu hình hiện có):

```powershell
python manage.py migrate
python manage.py setup_roles
python manage.py configure_library_defaults --username <tai_khoan_nhan_vien>
python manage.py expire_reservations
python manage.py refresh_overdue_loans
```

Lệnh cấu hình khởi tạo hạn mức sinh viên 5 tài liệu/14 ngày; giảng viên và nhân viên 10 tài liệu/30 ngày; một lần gia hạn 7 ngày; phạt quá hạn 1.000 đồng/ngày, trần 30.000 đồng. Báo/tạp chí, tài liệu quý/hiếm và luận văn/luận án bị đặt mặc định chỉ đọc tại chỗ; có thể sửa chính sách và chế độ lưu thông tại Admin theo quy định đã duyệt. Lệnh không tự đặt lịch mở cửa. Cần cấu hình `Library hours` và ngày nghỉ lễ/đóng cửa theo lịch thực tế để hạn trả và phạt tự lùi/tính đúng. Lập lịch `expire_reservations` mỗi 15 phút để xử lý hàng chờ, và `refresh_overdue_loans` mỗi ngày để cập nhật phạt đang phát sinh và chuyển trạng thái thẻ khi quá hạn đủ 7 ngày. Trang cổng bạn đọc cũng cập nhật phạt cho các lượt của chính bạn đọc đó.

Không nhập dữ liệu bạn đọc thật vào môi trường phát triển. Các giao dịch mượn/trả lưu người thao tác và lịch sử; tồn kho được quyết định từ từng bản sách có mã vạch, không dùng bộ đếm tồn kho trên đầu sách.
