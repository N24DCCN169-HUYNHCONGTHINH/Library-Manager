# Ngày 11 — Kiểm thử hồi quy, phân quyền và dữ liệu biên

Ngày cập nhật: 06/11/2026. Phạm vi: kiểm tra các luồng chính của MVP, tái hiện lỗi, sửa lỗi và chạy hồi quy. Không đưa hệ thống lên Internet hoặc chuyển dữ liệu desktop vào DB đang dùng.

## Lỗi đã sửa

| Vấn đề | Trước khi sửa | Kết quả sau sửa |
|---|---|---|
| Thu tiền bị gửi lại | Thu một phần hai lần từ cùng yêu cầu có thể tạo hai khoản thu. | Biểu mẫu mang UUID thao tác, lưu vào FinePayment với ràng buộc duy nhất. Cùng UUID trả lại biên nhận cũ; thay số tiền/khoản phạt/người thu/loại/lý do với UUID cũ bị từ chối. |
| Giữ chỗ hết hạn bị khôi phục ngoài ý muốn | Dọn giữ chỗ nằm trong cùng giao dịch mượn; nếu người hết hạn bị từ chối, việc chuyển hàng chờ cũng bị rollback. | Dọn giữ chỗ được gọi trước giao dịch mượn riêng trong luồng quầy thông thường. Yêu cầu bị từ chối không hồi sinh lượt giữ cũ. |
| Đặt trước trái chính sách | Có thể tạo yêu cầu dù chính sách hiện hành cấm mượn về. | Kiểm tra allow_home_loan trước khi tạo yêu cầu. |
| Gia hạn bản không còn được phép mượn | Bản bất hoạt/chỉ đọc tại chỗ hoặc chính sách hiện hành cấm vẫn có thể gia hạn. | Kiểm tra trạng thái bản, cờ hoạt động, hình thức mượn và chính sách hiện hành; vẫn dùng bản chụp số lần/ngày gia hạn đã lưu. |
| Tiền không hợp lệ trong service | NaN/chuỗi sai có thể gây lỗi chưa được xử lý; số lẻ VND có thể được chấp nhận khi gọi service trực tiếp. | Kiểm tra số nguyên hữu hạn, không âm/khác 0 theo nghiệp vụ, giới hạn số chữ số. Sai dữ liệu trả lỗi nghiệp vụ, không ghi khoản thu. Áp dụng cả số tiền duyệt bồi thường. |
| Tài khoản superuser bất hoạt | Service tin cờ superuser trước khi xét trạng thái hoạt động. | Tài khoản bất hoạt bị chặn kể cả khi gọi dịch vụ trực tiếp. |
| Metadata lời mời không hợp lệ khi bỏ qua form | Service có thể tạo hồ sơ sai mã/loại/ngày nếu được gọi trực tiếp. | full_clean tài khoản và hồ sơ trong giao dịch trước khi gửi email; sai dữ liệu hoàn tác cả tài khoản/hồ sơ. |

Miễn/giảm cũng bắt buộc ghi lý do; người duyệt phải có quyền và khác người thu theo quy định hiện có. Không sửa hoặc suy diễn lại các khoản thu cũ chưa có UUID; bảo vệ chống gửi lại áp dụng cho thao tác mới dùng biểu mẫu đã cập nhật.

Đã viết 6 kiểm thử hồi quy đầu tiên trước khi sửa và xác nhận các lỗi tương ứng tái hiện. Sau sửa, bổ sung kiểm thử HTTP thu tiền, quyền chỉ xem, tài khoản bất hoạt, lý do miễn giảm và kiểm tra metadata lời mời tại service.

## Ma trận kiểm tra

| Nhóm kiểm tra | Bằng chứng và kết quả |
|---|---|
| Đăng nhập, trạng thái, MFA | Bộ kiểm thử nền hiện có và test khóa/mở sau kích hoạt; đạt. |
| Kích hoạt tài khoản | Luồng HTTP nhận lời mời → đặt mật khẩu → đăng nhập; lời mời hết hạn và dùng lại bị chặn. Thẻ không tự được xác minh khi chỉ kích hoạt email. |
| Đổi email | Kiểm tra mật khẩu hiện tại; email chưa đổi trước xác nhận; GET liên kết chỉ hiện form, POST xác nhận mới đổi; sai mật khẩu không gửi thư. |
| Khóa/mở đăng nhập | Tài khoản đã xác minh email bị khóa và thu hồi phiên; mở lại đăng nhập được bằng mật khẩu hợp lệ. |
| Phân quyền | Giữ ma trận vai trò; tài khoản chỉ có quyền xem quầy không thể POST mượn/trả/gia hạn/thu tiền/xử lý hết hạn. Độc giả không xem hoặc thao tác hồ sơ người khác. |
| Lưu thông | Mượn/trả/gia hạn, hạn mức, FIFO, hủy/hết hạn giữ chỗ, nợ và chính sách được chạy lại toàn bộ. |
| Thao tác đồng thời | 8 kịch bản kiểm thử nhiều kết nối trên SQLite chạy lại đạt; khóa giữa hai kết nối PostgreSQL được kiểm tra riêng. |
| Thu tiền | Kiểm tra chống gửi lại tại service và HTTP, không thu trùng một phần; kiểm tra riêng trên PostgreSQL trong giao dịch hoàn tác. |
| Backup/restore | Backup PostgreSQL sau cập nhật gồm 514 bản ghi; khôi phục SQLite riêng và đối soát toàn bộ nội dung/FK đạt. |
| HTTPS nội bộ | Sau restart: health/login/static trả 200, POST khác origin 403, Host lạ 421, chứng chỉ được xác minh bằng CA riêng và cookie CSRF có Secure. |

## Kết quả cuối

- `manage.py test`: **114 kiểm thử đạt**, gồm 14 kiểm thử mới trong ngày 11 (11 hồi quy/phân quyền và 3 hành trình tài khoản).
- `manage.py check`: không có lỗi.
- `manage.py makemigrations --check --dry-run`: không có migration thiếu.
- `git diff --check`: đạt.
- Migration `library.0005_payment_idempotency` chỉ thêm trường UUID nullable/unique cho FinePayment, không thay số tiền/biên nhận cũ. Đã thử trên SQLite kiểm thử và áp cho bản khôi phục riêng, sau đó áp cho PostgreSQL phát triển bằng library_migrator/direct. Kết nối library_app/pooled xác minh TLS verify-full và không còn migration chờ.
- Không gửi email thật khi kiểm thử: dùng backend bộ nhớ. Dữ liệu tổng hợp thử trên PostgreSQL được hoàn tác, không giữ tài khoản hoặc khoản thu thử.
- Bản HTTPS localhost đã khởi động lại để dùng mã mới; ứng dụng cổng 8000 dùng DB phát triển có migration tương ứng.

Bằng chứng cục bộ: `work/day11/after-fixes-20261106.zip`, `work/day11/restore/verification.json` và `work/day10/https-verification.json`. Archive và dữ liệu khôi phục chứa thông tin tài khoản/MFA nên chỉ giữ cục bộ, không chia sẻ công khai. Với backup cũ cần đúng mã nguồn/migrations tương ứng như hướng dẫn ngày 10; bản backup sau sửa tương thích phiên bản hiện tại.

## Giới hạn và việc còn lại

- Đã giải quyết giới hạn kiểm thử PostgreSQL bằng nhánh QA do người dùng tạo: xem phần bổ sung bên dưới. Quyền tài khoản migrator của ứng dụng không được nâng; không chạy test runner/flush trên DB dùng chung.
- Chưa có đánh giá trực quan của người dùng, kiểm tra tải lớn, máy chủ công khai, DNS/chứng chỉ công cộng hoặc kiểm tra từ xa. HTTPS hiện vẫn là phiên nội bộ theo lựa chọn ngày 10.
- Các hạng mục đã ghi nhận trước đây vẫn còn: chuyển chính thức hồ sơ/loan/tài chính cũ cần mapping/căn cứ; lịch bảo trì tự động chưa đăng ký; các quy trình ngoại lệ mất/hỏng và nhắc hạn chưa được chứng nhận đầy đủ chỉ từ bộ kiểm thử này.
- Kết quả xác nhận các kịch bản đã chạy, không phải cam kết không còn lỗi hoặc đủ điều kiện vận hành thật. Không dùng số test đạt để quy đổi thành phần trăm tương đương thư viện thực tế.

Tiếp theo theo kế hoạch: ngày 12 — chạy thử bằng kịch bản dữ liệu tổng hợp và kiểm tra truy cập từ xa trong điều kiện hạ tầng cho phép; ngày 13 người dùng nghiệm thu và chốt các lỗi còn lại.

## Bổ sung: đã kiểm thử đầy đủ trên PostgreSQL QA

Người dùng đã tạo nhánh `library-qa-day11` và lưu kết nối riêng trong `web/.env.qa.local`. Vai trò owner trên QA có quyền tạo DB; cấu hình `config.qa` ghim đúng endpoint trực tiếp, từ chối endpoint trùng ứng dụng và chỉ cho chạy lệnh test. Test runner tạo DB mới `test_library_day11`, giữ nguyên `neondb` trên QA và nhánh production.

- PostgreSQL: 118 kiểm thử được xét, **116 đạt và 2 bỏ qua đúng phạm vi SQLite**; 8/8 kịch bản đồng thời đạt; tổng thời gian 425,094 giây.
- SQLite: **118/118 kiểm thử đạt**, gồm 4 kiểm tra bảo vệ cấu hình QA mới.
- Hai ca bỏ qua trên PostgreSQL kiểm tra nhập danh mục vào SQLite cục bộ; sản phẩm cố ý chặn nhập thử đó vào PostgreSQL. Chúng đều đạt ở lần chạy SQLite.
- Đã sửa thêm lỗi dữ liệu mặc định của migrations có thể làm bản khôi phục lệch snapshot. Sau migrate chỉ làm trống SQLite mới trong thư mục diễn tập rồi nạp đúng fixture; source không bị flush. Backup PostgreSQL cũng từ chối nằm trong giao dịch đã mở; test backup dùng giao dịch thực riêng phù hợp.
- Sau chạy, số dòng gốc trên QA ở các bảng tài khoản/sách/bản/lượt/thu tiền không đổi, DB kiểm thử đã được xóa.

Nhật ký và hướng dẫn chạy lại: [kiểm thử PostgreSQL QA](kiem-thu-postgresql-qa.md). Các giới hạn nghiệm thu giao diện, tải lớn, triển khai công khai, chuyển dữ liệu thật và lịch vận hành vẫn giữ nguyên; việc hoàn tất kiểm thử PostgreSQL không thay thế các bước đó.
