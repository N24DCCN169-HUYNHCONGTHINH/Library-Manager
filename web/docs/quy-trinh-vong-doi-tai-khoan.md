# Quy trình vòng đời tài khoản

## Cấp tài khoản

1. Quản lý thư viện đăng nhập Admin bằng tài khoản có Staff status và OTP.
2. Mở **Bảo mật tài khoản → Mời tài khoản**, nhập email, tên đăng nhập và vai trò.
3. Với độc giả, nhập mã bạn đọc, loại bạn đọc và thời hạn thẻ. Hệ thống tạo hồ sơ chưa xác minh, tài khoản bất hoạt và mật khẩu chưa được đặt.
4. Người nhận mở liên kết email trong 72 giờ, tự đặt mật khẩu. Chỉ sau bước này tài khoản mới được kích hoạt và email mới được đánh dấu đã xác minh.
5. Nhân viên xác minh danh tính/thẻ tại **Hồ sơ bạn đọc**. Nhật ký lưu người xác minh và thời điểm; trước đó hồ sơ không được mượn.
6. Nhân viên mới thuộc vai trò nghiệp vụ cần đăng ký TOTP trước khi vào khu vực nhân viên/Admin.

Không gửi mật khẩu chung. Lời mời có thể thu hồi hoặc gửi lại; mỗi liên kết chỉ dùng một lần và DB chỉ lưu mã băm token.

## Nguồn danh tính và phạm vi xác minh

- Trong giai đoạn thử nghiệm, quản lý thư viện cấp tài khoản bằng lời mời; không bật đăng ký công khai và không tự tạo tài khoản hàng loạt từ email.
- Với độc giả, thư viện đối chiếu mã bạn đọc và thời hạn thẻ với hồ sơ/thẻ hoặc danh sách chính thức do đơn vị quản lý cung cấp. Xác nhận email chỉ chứng minh người nhận kiểm soát hộp thư đó, không thay cho xác minh tư cách bạn đọc.
- Với nhân viên, quản lý thư viện cấp vai trò sau khi xác nhận họ thuộc đơn vị và cần quyền nghiệp vụ đó. `system_admin` chỉ dành cho người vận hành kỹ thuật; không cấp để giải quyết quyền nghiệp vụ.
- Nguồn dữ liệu định danh chính thức và nhà cung cấp SSO của đơn vị hiện chưa được chỉ định. Vì vậy chưa đồng bộ tự động và chưa liên kết SSO. Trước khi bật, chủ thư viện cần xác định đơn vị nào sở hữu danh sách, mã định danh ổn định, cách xử lý thôi học/nghỉ việc và người chịu trách nhiệm sửa dữ liệu sai.
- Nếu sau này tích hợp SSO hoặc đồng bộ danh sách, giữ mã định danh bên ngoài riêng với tên đăng nhập/email; không tự ghép hồ sơ chỉ vì email trùng. Tài khoản mới/đổi vai trò phải tiếp tục ghi actor, thời điểm và lý do.

## Đổi email và mật khẩu

- Đổi email yêu cầu mật khẩu hiện tại, gửi liên kết đến email mới và chỉ cập nhật sau khi người dùng đăng nhập đúng tài khoản rồi xác nhận liên kết trong 2 giờ.
- Khi đổi email, trạng thái xác minh email cũ bị xóa; xác nhận email mới sẽ đánh dấu email mới đã xác minh. Email cũ nhận cảnh báo nếu hệ thống có thể gửi.
- Đổi hoặc khôi phục mật khẩu được ghi vào nhật ký. Nhân viên chỉ nhận liên kết khôi phục tới email đã xác minh.
- Tài khoản tạo thủ công trong Django Admin bị buộc đổi mật khẩu ở lần đăng nhập đầu. Có thể yêu cầu đặt lại mật khẩu từ **Bảo mật tài khoản**.

## Khóa và hết hạn

- Quản lý có thể khóa/mở đăng nhập từ danh sách **Bảo mật tài khoản**. Mở lại yêu cầu email hiện tại đã xác minh. Khóa đăng nhập thu hồi TOTP và các phiên đang hoạt động.
- Thẻ độc giả hết hạn sẽ bị chặn giao dịch ngay theo ngày hiệu lực; chạy `python manage.py expire_reader_profiles` hằng ngày để cập nhật trạng thái và ghi nhật ký.
- Khóa đăng nhập và khóa thẻ là hai thao tác riêng. Giữ đăng nhập cho thẻ hết hạn để độc giả xem lịch sử và liên hệ thư viện.

## Khôi phục OTP bị mất

- Quản lý thư viện hoặc tài khoản kỹ thuật được cấp quyền chọn action **Thu hồi thiết bị xác thực OTP** trong **Bảo mật tài khoản**.
- Thu hồi xóa thiết bị OTP và đăng xuất mọi phiên người dùng. Khi đăng nhập lại, nhân viên phải đăng ký thiết bị mới.
- Nếu không vào được Admin, cán bộ được cấp quyền chạy lệnh trên máy chủ:

```powershell
python manage.py reset_totp_device <username> --actor <tai_khoan_duoc_uy_quyen>
```

Lệnh yêu cầu xác nhận tương tác; `--yes` bỏ qua xác nhận. Mỗi thao tác ghi người thực hiện, số thiết bị và số phiên bị kết thúc.

## Nhật ký

Các sự kiện tạo/kích hoạt/lời mời, xác minh hoặc đổi email, đặt lại mật khẩu, đổi vai trò, khóa/mở tài khoản và đăng ký/thu hồi OTP được lưu tại **Account security events**. Bản ghi chỉ đọc; người xóa tài khoản bị giới hạn bởi quan hệ lịch sử bảo mật.
