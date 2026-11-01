# Ma trận quyền nghiệp vụ

Quyền backend được cấp theo Django Groups và kiểm tra trong view/service. Trạng thái `Staff status` chỉ cho phép đăng nhập Django Admin; nó không tự cấp quyền nghiệp vụ. Superuser là tài khoản khẩn cấp, không dùng cho công việc thường ngày.

| Nghiệp vụ | reader | cataloger | circulation_staff | librarian (vai trò cũ) | library_manager | system_admin |
|---|---:|---:|---:|---:|---:|---:|
| Tra cứu danh mục công khai | Có | Có | Có | Có | Có | Có |
| Thêm/sửa đầu sách và bản sách | Không | Có | Không | Có | Có | Không |
| Xem hồ sơ bạn đọc trong nghiệp vụ | Chỉ hồ sơ mình | Không | Có | Có | Có | Không |
| Xác minh email/thẻ bạn đọc | Không | Không | Không | Có | Có | Không |
| Mượn/trả tại quầy | Không | Không | Có | Có | Có | Không |
| Đặt trước/gia hạn/hủy yêu cầu | Chỉ hồ sơ mình | Không | Không | Không qua cổng bạn đọc | Không qua cổng bạn đọc | Không |
| Thu tiền phạt | Không | Không | Có | Có | Có | Không |
| Miễn/giảm khoản phạt | Không | Không | Không | Không | Có, phê duyệt tách người thu | Không |
| Tạm khóa hồ sơ và gỡ hạn chế | Không | Không | Không | Không | Có | Không |
| Duyệt mất/hỏng và biểu phí | Không | Không | Không | Không | Có | Không |
| Sửa chính sách, lịch mở cửa, ngày nghỉ | Không | Không | Không | Không | Có | Không |
| Quản trị tài khoản kỹ thuật | Không | Không | Không | Không | Xem danh sách người dùng; quản lý vòng đời và lời mời theo quyền | Xem người dùng/nhóm; xem nhật ký bảo mật và thu hồi thiết bị OTP; không sửa nhóm hay dữ liệu nghiệp vụ |

## Cách đồng bộ vai trò

Sau khi migrate quyền mới, chạy `python manage.py setup_roles`. Lệnh đồng bộ chính xác các quyền của sáu nhóm chuẩn (thay thế quyền cấp trực tiếp cho chính các nhóm này); các quyền của superuser và thành viên cá nhân không bị sửa. Tài khoản cần vào Admin phải được bật `Staff status` riêng và vẫn chỉ thấy các mục phù hợp quyền.

## Hàng rào trong backend

- Dịch vụ mượn, trả, thu tiền và duyệt miễn/giảm kiểm tra permission ngay trong service; gọi service trực tiếp không vượt qua được quyền view.
- Độc giả chỉ gia hạn, đặt trước và hủy đặt trước bằng hồ sơ gắn với chính tài khoản đăng nhập. Truy vấn lịch sử, khoản phạt và đặt chỗ vẫn lọc theo hồ sơ đó.
- Người biên mục không được truy cập quầy lưu thông, thu tiền, sửa hồ sơ bạn đọc hay duyệt ngoại lệ.
- Lịch sử Loan/LoanRenewal/LoanEvent và sổ FinePayment chỉ đọc; không cấp quyền xóa lịch sử cho quản lý.
- Người duyệt miễn/giảm phải có quyền `approve_finepayment` và khác người thu tiền.

`system_admin` được xem thông tin bảo mật và thu hồi thiết bị OTP để hỗ trợ khôi phục, nhưng không được khóa/mở tài khoản, cấp lời mời, sửa nhóm hoặc xem dữ liệu lưu thông. Quản lý thư viện có thể mời và khóa/mở tài khoản theo các quyền riêng; quyền đó không biến thành quyền quản trị kỹ thuật.
