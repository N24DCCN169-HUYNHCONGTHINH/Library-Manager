# Hướng dẫn thành viên: từ máy mới đến chạy dự án

Tài liệu này dành cho thành viên mới dùng Windows. Mục tiêu là lấy đúng repository, chạy được website trên máy cá nhân và bắt đầu làm việc theo nhánh Git riêng.

## 1. Trạng thái dự án hiện tại

- Repository GitHub: <https://github.com/N24DCCN169-HUYNHCONGTHINH/Library-Manager>
- Ứng dụng desktop cũ nằm ở thư mục gốc repository.
- Dự án Django mới nằm trong `web/`.
- Nhánh `main` hiện có bộ khung Django.
- Nhánh `feat/book-catalog` đã được đẩy lên GitHub, có mô hình sách và trang quản lý sách trong Django Admin. Trước khi cả nhóm bắt đầu làm trên `main`, người phụ trách nên mở Pull Request và merge nhánh này vào `main`.
- Chưa có mô-đun độc giả, mượn trả, tiền phạt hoặc thanh toán trực tuyến.

## 2. Cài công cụ trên Windows

Cài các công cụ sau:

1. **Python 3.14** từ trang chính thức <https://www.python.org/downloads/windows/>. Giữ tùy chọn Python Launcher nếu trình cài đặt hiển thị.
2. **Visual Studio Code** từ <https://code.visualstudio.com/>.
3. **GitHub Desktop** từ <https://desktop.github.com/download/>.
4. Trong VS Code, cài phần mở rộng **Python** của Microsoft.

Mở PowerShell và kiểm tra Python:

```powershell
py -3.14 --version
```

Kết quả cần bắt đầu bằng `Python 3.14`. Nếu lệnh không nhận diện được, cài Python 3.14 và mở lại PowerShell.

## 3. Đăng nhập và clone repository

1. Mở GitHub Desktop, chọn **Sign in to GitHub.com** và đăng nhập.
2. Chọn **File → Clone repository**.
3. Chọn tab **URL** và dán:

   `https://github.com/N24DCCN169-HUYNHCONGTHINH/Library-Manager.git`

4. Chọn đường dẫn trên máy, ví dụ `D:\Library-Manager-Team\Library-Manager`, rồi bấm **Clone**.
5. Trong GitHub Desktop, chọn **Fetch origin** để cập nhật danh sách nhánh.
6. Nếu nhánh `feat/book-catalog` chưa được merge, báo người phụ trách merge Pull Request trước khi cả nhóm bắt đầu từ `main`.
7. Sau khi merge, chọn nhánh **main**, rồi bấm **Pull origin**.
8. Chọn **Repository → Open in Visual Studio Code**.

Không clone repository vào `D:\QuanLyThuVien_Web`; đó là dự án Django độc lập ban đầu, không phải bản clone của repository nhóm.

## 4. Tạo môi trường chạy Django

Trong VS Code, mở Terminal mới. Từ thư mục gốc repository, chạy:

```powershell
cd web
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
if (!(Test-Path .env)) { Copy-Item .env.example .env }
.\.venv\Scripts\python.exe manage.py migrate
```

Mỗi thành viên cần tạo `.venv` riêng trên máy của mình. Thư mục `.venv`, file `.env` và database SQLite không được đưa lên GitHub.

### Nếu PowerShell chặn `Activate.ps1`

Không cần kích hoạt môi trường ảo. Dùng trực tiếp `python.exe` bên trong `.venv` như các lệnh phía trên. Tránh đổi Execution Policy toàn máy.

### Nếu báo không tìm thấy `python.exe` trong `.venv`

Kiểm tra đang ở thư mục `web`:

```powershell
Get-Location
Test-Path .\.venv\Scripts\python.exe
```

Nếu lệnh thứ hai trả về `False`, tạo lại môi trường ảo trong `web`:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### Nếu báo `No module named django`

Đang dùng môi trường ảo chưa cài thư viện. Ở thư mục `web`, chạy:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 5. Chạy và đăng nhập

Khởi động máy chủ phát triển:

```powershell
.\.venv\Scripts\python.exe manage.py runserver
```

Giữ cửa sổ Terminal mở và vào <http://127.0.0.1:8000/>. Để vào Django Admin, mở <http://127.0.0.1:8000/admin/>.

Tạo tài khoản quản trị cho database trên máy của mình bằng một Terminal khác tại `web`:

```powershell
.\.venv\Scripts\python.exe manage.py createsuperuser
```

Tự đặt tên đăng nhập và mật khẩu. Nếu cổng 8000 đang được sử dụng, dừng máy chủ cũ bằng **Ctrl+C** rồi chạy lại.

Máy chủ `runserver` chỉ phục vụ phát triển trên máy cá nhân; chưa phải máy chủ để người ngoài truy cập.

## 6. Cách chia việc và làm việc chung

Mỗi đầu việc cần có GitHub Issue, người phụ trách và tiêu chí nghiệm thu. Nhóm dự kiến:

| Người | Việc chính | Kết quả cần có |
|---|---|---|
| Thịnh | Chốt nghiệp vụ, điều phối, kịch bản nghiệm thu và đối chiếu dữ liệu cũ | Quy tắc mượn/trả/phạt được viết rõ; có kịch bản để nhóm kiểm tra |
| Dũng Bùi | Tài khoản, đăng nhập và phân quyền | Nhân viên và độc giả đăng nhập được; độc giả chỉ truy cập dữ liệu của mình |
| Dũng Nguyễn | Sách và tra cứu | Nhân viên quản lý sách; độc giả tìm sách và xem số bản còn |
| Mạnh | Hồ sơ độc giả | Tạo/tìm/sửa hồ sơ và liên kết hồ sơ với tài khoản |
| Việt | Mượn, trả, gia hạn, đặt trước, tiền phạt | Tồn kho cập nhật đúng; hạn trả và phạt theo quy định đã chốt |

Trước khi làm song song, cả nhóm thống nhất các mô hình dữ liệu và trạng thái dùng chung. Người làm mượn trả cần phối hợp với người làm sách và độc giả.

## 7. Tạo nhánh, lưu thay đổi và mở Pull Request

Trong GitHub Desktop:

1. Chọn nhánh `main`, bấm **Fetch origin**, rồi **Pull origin**.
2. Chọn **Current Branch → New Branch**.
3. Đặt tên theo đầu việc, ví dụ `feat/readers` hoặc `feat/circulation`.
4. Sửa code trong VS Code; lưu file.
5. Quay lại GitHub Desktop, xem danh sách thay đổi.
6. Nhập mô tả ngắn ở **Summary**, ví dụ `Add reader profiles`, rồi bấm **Commit to ...**.
7. Bấm **Push origin** hoặc **Publish branch**.
8. Bấm **Create Pull Request**, chọn nhánh đích `main`, mô tả cách kiểm tra và nhờ một người khác review.

Không commit các file `web/.env`, `web/db.sqlite3`, thư mục `.venv`, bản sao lưu hay dữ liệu độc giả thật.

## 8. Nếu thích dùng PowerShell cho Git

Các lệnh dưới đây chạy từ thư mục gốc repository, không phải bên trong `web`:

```powershell
git switch main
git pull --ff-only origin main
git switch -c feat/ten-cong-viec
git add .
git commit -m "Describe the change"
git push -u origin feat/ten-cong-viec
```

Thay `ten-cong-viec` bằng tên nhánh phù hợp, ví dụ `feat/readers`. Mở Pull Request trên GitHub sau khi push.

### Lỗi `src refspec ... does not match any`

Tên nhánh trong lệnh push không trùng nhánh hiện tại, hoặc đang ở repo khác. Kiểm tra:

```powershell
git branch --show-current
git status
```

### Lỗi `rejected (fetch first)` khi đẩy `main`

Không đẩy trực tiếp lên `main`. Tạo nhánh riêng từ `main`, đẩy nhánh đó và mở Pull Request. Không dùng `git push --force`.

## 9. Quy trình kiểm tra trước Pull Request

- Chạy ứng dụng bằng `runserver` và thử luồng mình vừa sửa.
- Với thay đổi model, tạo và thêm migration vào Git:

  ```powershell
  .\.venv\Scripts\python.exe manage.py makemigrations
  .\.venv\Scripts\python.exe manage.py migrate
  ```

- Mở trang liên quan và xác nhận dữ liệu hiển thị đúng.
- Ghi trong Pull Request: mục đích, cách chạy và các bước đã kiểm tra.
- Nhờ một thành viên review trước khi merge.

## 10. Lịch làm việc 13 ngày

- **Ngày 1–2:** mọi người chạy được dự án; chốt quy định; thống nhất cấu trúc dữ liệu.
- **Ngày 3–7:** hoàn thành tài khoản, sách, độc giả và các luồng mượn trả cơ bản.
- **Ngày 8–10:** ghép chức năng; chuyển thử dữ liệu từ SQLite bằng bản sao và đối chiếu số lượng.
- **Ngày 11–12:** cả nhóm kiểm tra các kịch bản, sửa lỗi quan trọng.
- **Ngày 13:** demo nội bộ, ghi việc còn thiếu và xác định bước tiếp theo.

Để kịp thời hạn, ưu tiên mượn/trả và dữ liệu chính. Thanh toán trực tuyến chỉ thử ở môi trường sandbox nếu các luồng cốt lõi đã ổn định.
