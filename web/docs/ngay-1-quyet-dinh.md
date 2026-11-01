# Ngày 1 — Quy tắc nghiệp vụ và mô hình dữ liệu

> **Bản quy định tác nghiệp đầy đủ:** xem Phụ lục A trong tài liệu này. Phụ lục A là chuẩn nghiệp vụ hiện hành cho thiết kế MVP; phần quyết định ban đầu bên dưới được giữ làm biên bản Ngày 1 và lịch sử thay đổi.

Tài liệu này lưu quyết định nền tảng Ngày 1 (01/11/2026), mô hình dữ liệu ban đầu và nguồn tham khảo. Không dùng dữ liệu độc giả thật trong giai đoạn phát triển.

## 1. Quy tắc mượn, trả, gia hạn, đặt trước và phạt (đã chốt và cập nhật)

| Chủ đề | Quy tắc mặc định |
|---|---|
| Điều kiện mượn | Tài khoản và thẻ còn hiệu lực, không bị khóa, không có lượt mượn quá hạn, không có khoản phạt chưa thanh toán; còn hạn mức. Nếu có hồ sơ khiếu nại đang xử lý, tạm dừng cho mượn đến khi có quyết định. Chỉ cấp bản được phép mượn về. |
| Hạn mức | Theo loại độc giả: sinh viên tối đa 5 bản; giảng viên tối đa 10 bản; nhân viên tối đa 10 bản. Lưu loại độc giả tách biệt để sau này điều chỉnh riêng từng nhóm. |
| Thời hạn | 14 ngày lịch cho sinh viên; 30 ngày lịch cho giảng viên/nhân viên. Hạn trả là 23:59 giờ Việt Nam. Nếu ngày đến hạn trùng ngày thư viện thông báo đóng cửa cả ngày, tự dời sang ngày phục vụ kế tiếp. |
| Loại tài liệu | Mỗi nhan đề/bản có chính sách lưu thông: cho mượn về hoặc chỉ đọc tại chỗ. Mặc định chỉ đọc tại chỗ với tài liệu quý/hiếm, báo/tạp chí, luận văn/luận án; tài liệu tham khảo và giáo trình có thể được cấu hình mượn về với hạn mức/kỳ hạn riêng. |
| Gia hạn | Tối đa một lần, thêm 7 ngày tính từ hạn trả hiện tại. Chỉ thực hiện trong 2 ngày trước hạn, khi chưa quá hạn, không có người đặt trước và tài khoản còn đủ điều kiện. Không tự động gia hạn. |
| Đặt trước | Đặt theo nhan đề/ấn bản khi không còn bản cho mượn về sẵn sàng. FIFO theo thời điểm tạo; mỗi độc giả chỉ có một yêu cầu đang chờ cho cùng nhan đề. Khi bản được trả và kiểm tra xong, báo người đầu hàng và giữ 48 giờ; nếu hạn nhận kết thúc khi thư viện đóng cửa, kéo đến hết giờ phục vụ kế tiếp. Hết hạn thì chuyển người đủ điều kiện tiếp theo. |
| Trả | Tại quầy: thủ thư quét mã và xác nhận nhận sách; khi đó đóng lượt mượn, giải phóng hạn mức và chuyển bản sang sẵn sàng hoặc chờ xử lý tình trạng. Trả ngoài giờ chỉ bật nếu thư viện công bố điểm nhận và thực hiện đủ quy trình tại mục 1.1. |
| Nhắc hạn | Gửi nhắc trước hạn 3 ngày và trong ngày đến hạn; thông báo quá hạn mỗi 3 ngày cho đến khi trả. Email là kênh MVP; không nhận được thư không làm thay đổi hạn trả. Lưu trạng thái gửi/lỗi để nhân viên xử lý địa chỉ sai. |
| Quá hạn | 1.000 đồng/bản/ngày quá hạn, tính từ ngày sau hạn đến ngày trả xác nhận; không tính ngày lễ/Tết theo lịch nghỉ chính thức và ngày thư viện thông báo đóng cửa cả ngày. Mọi khoản mượn quá hạn chặn mượn mới ngay; quá hạn đủ 7 ngày chuyển tài khoản sang trạng thái `SUSPENDED` đến khi nhân viên xác nhận đã xử lý. |
| Mất/hỏng | Áp dụng quy trình phân loại và bồi thường tại mục 1.2. Quản lý phê duyệt, công bố trước biểu phí và tiêu chí; thủ thư áp dụng mức đã công bố. Chỉ trình quản lý duyệt riêng trường hợp ngoại lệ (tài liệu hiếm/không định giá được, tranh chấp, xin miễn/giảm). |
| Thanh toán | Thủ thư ghi khoản phải thu theo biểu phí đã duyệt, nhận tiền và cấp biên nhận; lưu từng lần thu và số dư. Miễn/giảm cần quyết định quản lý có lý do. Không tích hợp thanh toán trực tuyến trong MVP. |

### Cách tính và tình huống biên

- Phạt quá hạn được tính riêng cho từng `Loan` (mỗi dòng là một bản): `1.000đ × số_ngày_quá_hạn`; tổng nợ là tổng các khoản của độc giả. Không nhân thêm số bản lần nữa.
- Số ngày phạt là các ngày lịch sau ngày đến hạn, trừ ngày lễ/Tết theo lịch nghỉ chính thức và ngày thư viện thông báo đóng cửa cả ngày. Một ngày trễ được tính từ 00:00 sau ngày đến hạn; mốc trả là ngày trả được xác nhận (hoặc ngày khai trả hợp lệ qua thùng trả).
- Phạt không có trần cố định; dừng tích lũy khi xác nhận trả hoặc nhận khai báo mất hợp lệ. Nếu mất, không tiếp tục cộng phạt trong khi chờ định giá/duyệt bồi thường. Quản lý được miễn/giảm bằng quyết định có lý do và lưu vết.
- Trả đúng hạn hoặc sớm: 0 đồng phạt quá hạn.
- Mỗi lượt gia hạn cập nhật hạn trả và lưu thời điểm/người thực hiện; không sửa mất lịch sử.
- Hủy hoặc từ chối yêu cầu đặt trước không tạo khoản mượn hay khoản phạt.
- Không cho mượn vượt tồn kho, hạn mức hoặc giữ chỗ đã cấp. Cập nhật trạng thái bản sách trong một giao dịch để hai yêu cầu đồng thời không lấy cùng một bản.
- Nếu thư viện bật thùng trả ngoài giờ, dùng mốc khai trả có biên nhận hợp lệ để tính ngày trả khi nhân viên kiểm tra trong ca làm việc kế tiếp.
- Tài liệu chỉ đọc tại chỗ không tạo `Loan`; lượt sử dụng tại chỗ có thể ghi bằng một loại giao dịch riêng nếu nhóm cần thống kê.

### 1.1. Quy trình trả ngoài giờ / thùng trả sách

Tham khảo dịch vụ trả ngoài giờ của Thư viện Trường ĐH KHXH&NV, ĐHQG-HCM: bạn đọc khai form trước, bỏ sách vào khe trả, rồi kiểm tra email xác nhận; dịch vụ chỉ nhận sách nguyên vẹn, chưa quá hạn và không quá 1.000 trang. Tài liệu ngoài điều kiện phải trả tại quầy trong giờ phục vụ. Đây là dịch vụ theo địa điểm và lịch riêng của trường.

**Quy trình đề xuất cho MVP nếu thư viện bật tính năng này:**

1. Chỉ nhận sách tại điểm trả được thư viện công bố. Bạn đọc quét QR/điền form, khai mã độc giả và từng mã bản sách; hệ thống cấp biên nhận `DROP_REPORTED` với mã duy nhất và thời gian máy chủ, nhưng lượt mượn vẫn ở trạng thái chờ nhận.
2. Chỉ nhận sách nguyên vẹn, chưa quá hạn tại thời điểm gửi, không phải tài liệu chỉ đọc tại chỗ/khổ lớn, và tối đa 1.000 trang. Trả sách quá hạn hoặc hỏng phải thực hiện tại quầy để nhân viên lập hồ sơ trực tiếp.
3. Nhân viên thu sách mỗi ca phục vụ, quét mã, đối chiếu biên nhận và kiểm tra tình trạng. Lưu `drop_reported_at`, `staff_received_at`, `inspected_at`, nhân viên xử lý và ghi chú/ảnh khi có bất thường.
4. Sách nguyên vẹn, đúng mã và khớp biên nhận: xác nhận trả với ngày trả là ngày khai báo; giải phóng hạn mức và dừng phạt tại ngày đó. Nhân viên phải kiểm tra trong ca phục vụ kế tiếp.
5. Sách thiếu, sai mã hoặc có dấu hiệu hư hỏng: chuyển `RETURN_REVIEW`, vẫn giữ biên nhận và thời điểm gửi; nhân viên liên hệ độc giả, lập hồ sơ kiểm tra. Không tính phạt cho khoảng thời gian nhân viên xử lý. Quản lý quyết định nếu có bằng chứng biên nhận không khớp hoặc thông tin khai báo sai.
6. Nếu hệ thống/QR lỗi, dùng phiếu giấy có số thứ tự và thời điểm do nhân viên trực ghi; nhập bổ sung sau khi hệ thống hoạt động. Điểm trả phải có lịch lấy sách và người chịu trách nhiệm; nếu chưa bố trí được các điều kiện này thì chưa mở dịch vụ.

**Giới hạn khởi đầu:** Bản đang chờ nhân viên xác nhận chưa sẵn sàng cho người đặt trước hoặc lượt mượn mới. Mốc gửi chỉ có giá trị khi có biên nhận hợp lệ và đối chiếu được mã bản sách.

### 1.2. Quy trình sách mất hoặc hư hỏng

Các nguồn trong thành phố không dùng chung một biểu giá. Bộ quy tắc dưới đây vay mượn ưu điểm là có phương án thay thế sách và phí xử lý minh bạch, nhưng thống nhất một quy trình cho MVP. Mức bồi thường thực tế phải được quản lý thư viện duyệt và biểu phí cần được công bố trước khi áp dụng.

**Luồng xử lý:**

1. **Ghi nhận trước và sau mượn:** Nhân viên lưu tình trạng bản lúc cấp; bạn đọc báo ngay rách, bẩn, thiếu trang có sẵn trước khi nhận. Khi trả, nhân viên kiểm tra; nếu có vấn đề, tạo `DamageCase` và cho độc giả ghi ý kiến.
2. **Phân loại:** `NORMAL_WEAR` (hao mòn tự nhiên, không thu), `MINOR_DAMAGE` (có thể sửa), `MAJOR_DAMAGE` (không thể lưu thông), `LOST`. Lưu mã bản/lượt mượn, mô tả, ảnh/chứng từ, người kiểm tra, thời điểm và ý kiến độc giả.
3. **Bảo toàn lịch sử và dừng phạt:** Bản `DAMAGED`/`LOST` không được cho mượn. Không xóa lượt mượn. Dừng phạt trễ khi thư viện xác nhận nhận sách hoặc nhận được khai báo mất có mã hồ sơ; không cộng phạt trong thời gian thư viện điều tra/duyệt.
4. **Áp dụng biểu phí đã duyệt:** Hao mòn tự nhiên không thu. Hư nhẹ thu chi phí sửa chữa thực tế có chứng từ, tối đa bằng giá thay thế hiện hành. Mất hoặc hỏng nặng: độc giả nộp bản cùng nhan đề và ấn bản hiện hành/tương đương có giá trị không thấp hơn, cộng phí xử lý theo biểu phí công khai; nếu không thể tìm bản thay thế, mức bồi thường là 3 lần giá mua thay thế hiện hành cộng phí xử lý. Thủ thư tính theo biểu phí và tiêu chí đã được quản lý phê duyệt, thông báo căn cứ và cấp biên nhận; không tự chọn mức giá.
5. **Chuyển trường hợp ngoại lệ:** Tài liệu quý/hiếm, không có giá thay thế đáng tin cậy, tranh chấp về tình trạng/trách nhiệm, hoặc yêu cầu miễn/giảm phải trình quản lý quyết định trước khi chốt khoản phải thu. Ghi rõ lý do, bằng chứng và quyết định. Trong khi chờ giải quyết, tạm chặn mượn mới nhưng không tính thêm tiền phạt. Độc giả có 5 ngày làm việc để gửi phản hồi/khiếu nại; khoản đang tranh chấp chưa thu cho đến khi có quyết định.
6. **Hoàn tất:** Thủ thư nhận bản thay thế/tiền theo mức đã duyệt, cấp biên nhận; đánh dấu `SETTLED`, cập nhật tình trạng bản và lưu người thực hiện/thời điểm. Nếu sách được tìm thấy trước khi bồi thường hoàn tất, hủy hồ sơ mất và kiểm tra tình trạng. Nếu tìm thấy sau khi đã nhận bồi thường, quản lý quyết định hoàn trả/đối trừ sau khi trừ chi phí thực tế đã phát sinh.

Khoản phạt quá hạn và khoản bồi thường là hai khoản riêng. Nợ phạt chưa thanh toán chặn mượn theo điều kiện chung; trạng thái `SUSPENDED` áp dụng khi có khoản mượn quá hạn đủ 7 ngày hoặc hồ sơ mất/hỏng cần xác minh.

### Tham khảo để chọn chính sách

- Thư viện Khoa học Tổng hợp TP.HCM công bố gói mượn về nhà tối đa 2 tài liệu/lần, giá trị sách theo gói và thời gian giữ tối đa 30 ngày; FAQ hiện hành cũng nêu không có chính sách gia hạn và phí quá hạn 2.000 đồng/ngày/cuốn khi giữ quá 30 ngày. Đây là dịch vụ/gói cụ thể của thư viện, không áp dụng nguyên xi cho dự án.
- Nội quy công khai của Trung tâm Thông tin – Thư viện PTIT phân biệt đối tượng và tài liệu: quy định được lập chỉ cho mượn một số loại, sinh viên 2 cuốn/7 ngày, cán bộ giảng viên tối đa 3 cuốn thông thường hoặc 8 cuốn theo môn học/150 ngày. Bản nội quy được đăng lâu năm; cần xác nhận với cơ sở TP.HCM trước khi dùng làm chuẩn hiện hành.
- Quy trình công khai của Thư viện Trường ĐH KHXH&NV, ĐHQG-HCM kiểm tra tình trạng nợ tài liệu/nợ phí/khóa tài khoản trước khi cho mượn. Quy trình thu phí của ĐH Mở TP.HCM đưa ví dụ mức 1.000 đồng/cuốn/ngày; sách mất/hỏng được xử lý theo lựa chọn đền sách hoặc đền tiền và phí xử lý. Các mức bồi thường thuộc quy định riêng của trường đó.
- Các nội quy tham khảo khác nhau; nhóm đã chọn bộ quy tắc cụ thể ở bảng phía trên làm chính sách của MVP, không sao chép nguyên mức phí hay hạn mức của thư viện tham khảo.

## 2. Mô hình dữ liệu thống nhất

Thống nhất danh từ và quan hệ trước khi chia nhánh. Đề xuất quản lý tồn kho theo **từng bản sách vật lý**; `Book.available_copies` hiện có chỉ là số đếm khởi đầu, không đủ làm nguồn sự thật khi có mượn đồng thời.

| Mô hình | Trường chính | Quan hệ / quy tắc |
|---|---|---|
| `User` (Django) | tên đăng nhập, mật khẩu băm, email, trạng thái | Dùng nhóm/quyền Django cho nhân viên và độc giả; không lưu mật khẩu riêng. |
| `Reader` | `user` (tùy chọn với hồ sơ nhập cũ), mã độc giả, loại độc giả, ngày bắt đầu/kết thúc quyền sử dụng, trạng thái | Mã duy nhất; loại gồm sinh viên, giảng viên, nhân viên. Một hồ sơ có thể liên kết một tài khoản; lưu hồ sơ cũ dù không đăng nhập được. Chỉ hỗ trợ các nhóm này trong MVP. |
| `CirculationPolicy` | loại độc giả, loại tài liệu, hạn mức, số ngày mượn, số lần/số ngày gia hạn, cho phép đặt trước | Lưu quy tắc thành dữ liệu cấu hình để điều chỉnh không cần sửa code; áp dụng theo nhóm và loại tài liệu. |
| `Book` | mã đầu sách, tên, tác giả, thể loại, nhà xuất bản, năm, ấn bản, loại tài liệu, giá thay thế tham chiếu | Một đầu sách có nhiều bản vật lý; giá tham chiếu cần nguồn và ngày cập nhật. |
| `BookCopy` | mã vạch duy nhất, `book`, trạng thái, được mượn về hay không, ghi chú tình trạng | Mỗi bản có trạng thái `AVAILABLE`, `ON_LOAN`, `ON_HOLD`, `RETURN_REVIEW`, `LOST`, `DAMAGED`; chỉ cấp bản `AVAILABLE` được phép mượn về. |
| `Loan` | `reader`, `copy`, người lập, thời điểm mượn, hạn trả, thời điểm trả, số lần gia hạn, trạng thái | Mỗi dòng là một bản sách; tiền phạt tính theo từng `Loan`. Lưu lịch sử sự kiện gia hạn/trả, không xóa giao dịch. |
| `Reservation` | `reader`, `book`, thời điểm tạo, trạng thái, hạn nhận | Xếp hàng theo thời điểm tạo; trạng thái `PENDING`, `READY`, `FULFILLED`, `CANCELLED`, `EXPIRED`. |
| `Fine` | `loan`, mức phạt/ngày tại thời điểm phát sinh, ngày bắt đầu/kết thúc, số ngày tính, số tiền, trạng thái | Một khoản phạt gắn với một `Loan`; lưu ảnh chụp mức giá/quy tắc để lịch sử không đổi khi biểu phí được sửa. |
| `FinePayment` | `fine`, số tiền thu/miễn/điều chỉnh, thời điểm, nhân viên, mã biên nhận, lý do | Ghi từng lần thanh toán, hoàn/miễn/điều chỉnh; số dư tính từ sổ giao dịch, hỗ trợ thanh toán một phần. |
| `ReturnReceipt` | `loan`, mã bản, thời điểm bạn đọc khai trả, thời điểm nhân viên nhận, thời điểm kiểm tra, trạng thái, người nhận | Dùng cho trả ngoài giờ; lưu bằng chứng khai báo và xác nhận riêng biệt. |
| `DamageCase` | `loan`, `copy`, loại sự cố, mô tả/bằng chứng, ý kiến độc giả, trạng thái, phương án, số tiền được duyệt, người duyệt, khiếu nại | Theo dõi mất/hỏng tách khỏi phạt trễ; chỉ tạo khoản phải thu sau khi phương án và số tiền được duyệt. |

### Quy ước chung

- Dùng khóa chính số của Django; các mã nghiệp vụ (mã sách, mã vạch, mã độc giả) có ràng buộc duy nhất.
- Dùng `DecimalField` cho tiền, không dùng số thực. Thời điểm dùng `DateTimeField` và UTC ở DB (`USE_TZ=True`); giao diện hiển thị giờ Việt Nam.
- Không xóa cứng hồ sơ đã phát sinh giao dịch; dùng trạng thái ngừng hoạt động. Ràng buộc xóa dùng `PROTECT` cho lịch sử mượn/phạt.
- Mọi luồng mượn, trả, cấp giữ chỗ cập nhật tồn kho trong `transaction.atomic`; khóa bản sách khi cần để tránh cấp trùng.
- Ảnh bìa và thông tin nhạy cảm không đưa vào log; dữ liệu demo phải tổng hợp.

## 3. Trạng thái ngày 1 trên máy hiện tại

- Repository web: `D:\Library-Manager\web` (nhánh `feat/book-catalog`).
- Hướng dẫn thành viên đã có ở `docs/huong-dan-thanh-vien.md`; mỗi thành viên cần làm theo để xác nhận trên máy riêng.
- Mô hình `Book` hiện tại đã có; `BookCopy`, `Reader`, `Loan`, `Reservation`, `Fine` là phần sẽ xây ở các ngày sau sau khi nhóm thống nhất quyết định này.
- Bộ quy tắc tại mục 1 đã được nhóm chốt và có thể dùng làm tiêu chí triển khai, gồm các trường hợp mất/hỏng cần người có thẩm quyền duyệt.

## 4. Xác nhận của nhóm

Nhóm đã chốt các mức nền tảng tại mục 1 ngày 01/11/2026. Các điều kiện vận hành bổ sung trong tài liệu này được điều phối viên yêu cầu đưa vào đặc tả MVP. Quản lý thư viện duyệt/công bố biểu phí và tiêu chí bồi thường trước khi thu; thủ thư xử lý theo mức chuẩn, chỉ trình duyệt riêng các trường hợp ngoại lệ. Thư viện chỉ bật thùng trả sau khi có điểm nhận, lịch lấy sách và người chịu trách nhiệm. Mỗi thành viên tiếp tục xác nhận môi trường chạy theo hướng dẫn cài đặt.

## 5. Nguồn tham khảo

Bản đối chiếu chi tiết với thư viện tại TP.HCM nằm ở Phụ lục C; checklist tình huống và phương án xử lý nằm ở Phụ lục B.

- [FAQ — Thư viện Khoa học Tổng hợp TP.HCM](https://thuvientphcm.gov.vn/nhung-cau-hoi-thuong-gap1)
- [Dịch vụ mượn về — Thư viện Khoa học Tổng hợp TP.HCM](https://thuvientphcm.gov.vn/phuc-vu-ban-doc/dich-vu-muon-ve-new)
- [Nội quy thư viện — Trung tâm Thông tin – Thư viện PTIT](https://lib.ptit.edu.vn/noi-quy-thu-vien/)
- [Quy trình mượn tài liệu — Thư viện Trường ĐH KHXH&NV, ĐHQG-HCM](https://hcmussh.edu.vn/static/document/quytrinhmuontailieuvenha.pdf)
- [Quy trình thu tiền phạt mượn quá hạn và làm hỏng, mất tài liệu — Thư viện ĐH Mở TP.HCM](https://v1.ou.edu.vn/hcqt/Quy%20trnh/TV.05.pdf)
- [Dịch vụ trả tài liệu ngoài giờ phục vụ — Thư viện Trường ĐH KHXH&NV, ĐHQG-HCM](https://hcmussh.edu.vn/cilm/dich-vu-mien-phi)
- [Quy định mượn liên thư viện về xử lý mất/hư hỏng — Thư viện Trường ĐH KHXH&NV, ĐHQG-HCM](https://hcmussh.edu.vn/cilm/muon-lien-thu-vien)
- [Nội quy thư viện — Trường ĐH Sư phạm TP.HCM](https://thuvien.hcmue.edu.vn/node/85)

---

## Phụ lục A — Quy định mượn, trả, đặt trước và bồi thường (bản cập nhật MVP)

**Trạng thái:** Bản quy định cập nhật theo yêu cầu điều phối viên; giữ các hạn mức cốt lõi nhóm đã chốt và đề xuất mặc định cho những tình huống checklist còn thiếu. Chỉ dùng làm chính sách vận hành sau khi nhóm/quản lý thư viện duyệt bản cập nhật.
**Áp dụng:** Sinh viên, giảng viên và nhân viên có hồ sơ độc giả còn hiệu lực. MVP không phục vụ khách ngoài hoặc mượn liên thư viện.

Phụ lục A là nguồn quy định có hiệu lực cho thiết kế MVP. Nếu nội dung ở phần quyết định ban đầu, Phụ lục B hoặc Phụ lục C khác Phụ lục A, áp dụng Phụ lục A; các phần kia lưu biên bản, checklist và căn cứ tham khảo.

### 1. Nhóm độc giả và điều kiện mượn

| Nhóm độc giả | Số bản mượn tối đa | Thời hạn chuẩn |
|---|---:|---:|
| Sinh viên | 5 | 14 ngày lịch |
| Giảng viên | 10 | 30 ngày lịch |
| Nhân viên | 10 | 30 ngày lịch |

- Mỗi người có một hồ sơ độc giả chuẩn với mã duy nhất và một tài khoản đăng nhập; nếu có nhiều mã cũ, quản lý gộp hồ sơ và giữ nguyên lịch sử.
- Tài khoản được mượn khi hồ sơ/thẻ đang hiệu lực, không có lượt mượn quá hạn, không còn số dư phạt, không bị tạm chặn do hồ sơ khiếu nại/mất-hỏng đang xử lý, còn hạn mức và loại tài liệu cho phép mượn về.
- Hạn mức đếm **số bản vật lý đang mượn**. Yêu cầu đặt trước/giữ sách chưa nhận không chiếm hạn mức; khi nhân viên hoàn tất giao dịch mượn mới tính vào hạn mức.
- Người đổi nhóm độc giả được áp dụng quota/kỳ hạn mới cho giao dịch mượn mới. Các lượt đang mở giữ nguyên hạn và mức phạt đã chụp tại thời điểm mượn. Thẻ hết hạn chặn mượn/gia hạn mới nhưng người đọc vẫn được trả sách, thanh toán và khiếu nại.
- Tốt nghiệp/nghỉ việc/chuyển trường không xóa lịch sử; tài khoản hết hiệu lực phải hoàn tất lượt mượn và số dư. Cán bộ hệ thống có hồ sơ độc giả riêng nếu họ cũng mượn sách; quyền nhân viên hệ thống không tự sinh quyền mượn.
- Người mượn phải xuất trình thẻ/tài khoản của chính mình; không cho mượn hộ. Người khác được trả hộ nhưng không được xem nợ, lịch sử hoặc thông tin riêng của chủ tài khoản.
- MVP không cho người ngoài đăng ký. Khi mất thẻ, khóa thẻ cũ và cấp mã mới liên kết cùng hồ sơ; không tạo hồ sơ mới để né hạn mức/nợ.
- Chỉ quản lý được khóa/mở tài khoản thủ công; nhập lý do, thời gian bắt đầu và người thực hiện. Khóa thủ công không xóa hay dời hạn của loan hiện có.

### 2. Loại tài liệu và tồn kho

- Quản lý số lượng theo từng `BookCopy` có mã vạch; `Book.available_copies` không phải nguồn tồn kho nghiệp vụ sau khi đưa mô hình bản vật lý vào dùng.
- Mỗi đầu sách/bản sách có chính sách `HOME_LOAN` (được mượn về) hoặc `IN_LIBRARY_ONLY` (chỉ đọc tại chỗ). Mặc định tài liệu quý/hiếm, báo/tạp chí, luận văn/luận án chỉ đọc tại chỗ. Sách tham khảo/giáo trình được cấu hình riêng theo loại, không mặc định cấm hoặc cho mượn toàn bộ.
- Bản đang mượn, giữ cho người đặt trước, chờ kiểm tra trả, hỏng, mất, kiểm kê hoặc không tìm thấy không được tính là bản sẵn có.
- Sách bộ/nhiều tập có mã bản riêng cho từng vật phẩm. Chính sách thay thế/đền bù áp theo tập bị mất; nếu không thể bổ sung riêng một tập thì quản lý duyệt giá trị cả bộ theo biểu phí.
- Thêm, sửa giá tham chiếu, thay trạng thái, thanh lý hoặc gộp bản cần lưu người thực hiện, thời điểm, lý do và giá trị trước/sau. Giá tham chiếu cần nguồn và ngày cập nhật.

### 3. Lập lượt mượn và hạn trả

- Thủ thư xác minh tài khoản, nhóm độc giả, quyền lưu thông của bản, số bản đang mượn, nợ và trạng thái giữ chỗ trước khi lập lượt.
- Một dòng `Loan` là một bản vật lý. Mượn nhiều bản là nhiều lượt liên kết cùng giao dịch quầy; từng bản có hạn, trạng thái trả và phạt riêng. Nếu một bản không hợp lệ, thủ thư báo rõ bản đó; các bản hợp lệ vẫn có thể giao dịch riêng, không giữ bản không hợp lệ.
- Lượt mượn chỉ thành công khi cả loan và trạng thái bản được ghi nguyên tử. Hai yêu cầu đồng thời tranh bản cuối/hạn mức chỉ có một yêu cầu được chấp nhận. Gửi lại cùng thao tác do mạng chậm không được sinh giao dịch thứ hai.
- Ngày mượn là ngày địa phương tại `Asia/Ho_Chi_Minh`; ngày mượn là ngày 0. Hạn chuẩn là ngày mượn cộng 14 hoặc 30 ngày lịch, đến 23:59 giờ Việt Nam.
- Nếu ngày đến hạn rơi đúng ngày thư viện đã công bố đóng cửa cả ngày, hạn chuyển đến 23:59 của ngày phục vụ tiếp theo. Đóng cửa một phần ngày không tự dời hạn. Nếu có đóng cửa khẩn cấp sau khi hạn đã được công bố, ngày đóng cửa được miễn tính phạt; quản lý có thể ban hành dời hạn hàng loạt và lưu quyết định.
- Lượt mượn lưu bản chụp loại độc giả, loại tài liệu, hạn mức, hạn trả và phiên bản chính sách tại thời điểm giao dịch. Chính sách mới chỉ áp dụng cho lượt mượn tạo sau ngày hiệu lực.
- Gia hạn trực tuyến và tại quầy dùng cùng điều kiện. Chỉnh ngày hạn thủ công chỉ cho quản lý, phải nhập lý do và lưu hạn cũ/mới; thao tác này không tiêu thụ lượt gia hạn.

### 4. Gia hạn

- Mỗi lượt được gia hạn tối đa một lần thêm 7 ngày lịch, tính từ hạn trả hiện tại. Nếu hạn mới rơi vào ngày thư viện đóng cửa cả ngày, chuyển sang ngày phục vụ kế tiếp.
- Cửa sổ gia hạn bắt đầu đúng 48 giờ trước hạn hiện tại và kết thúc tại hạn hiện tại; dùng thời điểm hệ thống theo giờ Việt Nam. Không gia hạn quá hạn.
- Chỉ cho gia hạn khi không có reservation đang chờ hoặc đã sẵn sàng cho cùng nhan đề/ấn bản, tài khoản đủ điều kiện, không có nợ và chính sách loại tài liệu cho phép.
- Việc gia hạn và cấp một bản cho người đặt trước được tuần tự hóa: giao dịch nào được ghi thành công trước quyết định kết quả; không thể vừa gia hạn vừa chuyển bản sang giữ chỗ.
- Yêu cầu bị từ chối giữ nguyên hạn hiện tại, không tạo phạt. Lưu thời điểm, người thao tác, hạn cũ/mới và lý do.

### 5. Đặt trước và hàng chờ

- Được đặt trước theo nhan đề/ấn bản cụ thể khi không còn bản `HOME_LOAN` sẵn sàng. Nếu có bản đủ điều kiện sẵn, độc giả mượn trực tiếp.
- Mỗi độc giả chỉ có một yêu cầu đang chờ cho cùng nhan đề/ấn bản. Yêu cầu đã hủy/hết hạn không còn hoạt động; độc giả được đặt lại ở cuối hàng.
- FIFO theo timestamp máy chủ; trường hợp bằng timestamp dùng mã yêu cầu làm thứ tự phụ. Nếu nhiều bản trả cùng lúc, cấp từng bản lần lượt theo thứ tự queue.
- Khi bản được kiểm tra và chuyển sang `ON_HOLD`, thông báo hiển thị trong tài khoản và gửi email. Thời gian nhận là 48 giờ thực kể từ lúc thông báo hiển thị trong tài khoản. Nếu thư viện đóng cửa tại đúng thời điểm hết hạn, kéo đến hết giờ phục vụ kế tiếp. Nếu hệ thống thông báo/tài khoản ngừng hoạt động, đồng hồ giữ chỗ tạm dừng cho đến khi có kênh thông báo hoạt động và có dấu thời gian.
- Bản giữ chỗ chưa chiếm quota nhưng độc giả phải đủ điều kiện khi đến nhận. Nếu chưa đủ điều kiện hoặc không nhận kịp, bỏ lượt giữ chỗ hiện tại, thông báo rõ lý do và chuyển bản cho người kế tiếp; độc giả có thể đặt lại ở cuối hàng sau khi đủ điều kiện.
- Nếu email trả về lỗi nhưng thông báo tài khoản vẫn hiển thị, thời gian giữ tính từ lúc hiển thị trong tài khoản. Nếu cả tài khoản và email đều không gửi/hiển thị được, chưa bắt đầu thời gian giữ.
- Hết thời gian nhận, hủy, hoặc người đầu hàng không đủ điều kiện thì chuyển cho người kế tiếp; lưu lý do và không tạo loan/phạt cho người không nhận. Nếu không còn bản lưu thông được, dừng queue và báo người đang chờ.

### 6. Trả tại quầy và trả ngoài giờ

#### Trả tại quầy

- Nhân viên quét mã bản và xác nhận đã nhận vật phẩm; cho phép người khác trả hộ nhưng không tiết lộ thông tin tài khoản của người mượn.
- Khi đã nhận và quét đúng bản, đóng loan, giải phóng quota và dừng tính phạt theo ngày trả. Nếu có dấu hiệu hỏng/thiếu trang, bản chuyển `RETURN_REVIEW`, không sẵn sàng cho mượn; hồ sơ bồi thường xử lý riêng.
- Quét trả lặp, loan đã đóng, bản không khớp, hoặc mã không tồn tại phải báo lỗi/đã trả; không tạo giao dịch mới, không tăng tồn kho hai lần. Thủ thư dùng bước sửa sai có lý do/audit khi quét nhầm.

#### Thùng trả ngoài giờ

- Chỉ bật tại điểm có lịch lấy sách và người chịu trách nhiệm. Nhận sách nguyên vẹn, chưa quá hạn, loại được mượn về, không quá 1.000 trang/khổ đặc biệt. Sách quá hạn hoặc đã hỏng phải trả trực tiếp tại quầy.
- Bạn đọc khai từng mã bản qua QR/form; hệ thống cấp biên nhận duy nhất `DROP_REPORTED` kèm timestamp máy chủ. Khi biên nhận hợp lệ và mã bản đúng, thư viện coi đã nhận quyền kiểm soát sách tại mốc đó: đóng loan, giải phóng quota và dừng phạt ngay; bản chuyển `RETURN_PENDING`, chưa thể cho mượn/đặt trước trước khi kiểm tra.
- Nhân viên lấy/kiểm tra sách trong ca phục vụ kế tiếp, lưu `drop_reported_at`, `staff_received_at`, `inspected_at`, người xử lý và tình trạng. Nếu không tìm thấy sách trong thùng hoặc sai mã, mở hồ sơ điều tra; không tự động khôi phục tiền phạt. Quản lý xem bằng chứng và quyết định; chỉ điều chỉnh khoản phí nếu xác định biên nhận không hợp lệ/sai sự thật, có giải trình và quyền khiếu nại.
- Nếu thùng bị đầy/hỏng hoặc QR/hệ thống ngừng hoạt động, nhân viên trực cấp phiếu giấy có số tuần tự và giờ ghi; nhập lại bằng cùng mã biên nhận để chống trùng. Không có điểm nhận/người phụ trách thì không cung cấp dịch vụ.
- Sách có dấu hiệu hỏng sau khi bỏ thùng vẫn đóng loan và dừng phạt ở mốc khai báo hợp lệ; chuyển `RETURN_REVIEW` và xử lý DamageCase. Không quy trách nhiệm chỉ dựa trên phát hiện sau khi nhân viên mở thùng.

### 7. Tiền phạt quá hạn và trạng thái tài khoản

- Phạt 1.000 đồng cho mỗi ngày quá hạn đủ điều kiện, tính riêng từng bản/loan. Ngày mượn là ngày 0; hạn đến 23:59; ngày đầu tính phạt là ngày địa phương tiếp theo sau hạn. Tính đến ngày trả được xác nhận hoặc ngày khai trả ngoài giờ hợp lệ.
- Loại trừ ngày lễ/Tết theo lịch nghỉ chính thức và ngày thư viện công bố đóng cửa cả ngày. Ngày đóng một phần vẫn tính như ngày bình thường. Lịch nghỉ có phiên bản/ngày hiệu lực để giải thích lại khoản phạt.
- **Trần phạt đề xuất:** tối đa 30.000 đồng cho một bản; nếu giá thay thế đã được quản lý xác nhận thấp hơn 30.000 đồng thì trần bằng giá thay thế đó. Nếu chưa có giá, trần tạm thời là 30.000 đồng. Khi chạm trần, ngừng tăng tiền và chuyển `LONG_OVERDUE_REVIEW`; không tự kết luận sách đã mất.
- Nếu loan đang `LONG_OVERDUE_REVIEW`, mượn mới vẫn bị chặn. Nhân viên liên hệ độc giả; trạng thái chỉ đóng khi sách được trả, được xác nhận mất và xử lý bồi thường, hoặc quản lý có quyết định khác được lưu vết.
- Mọi loan quá hạn chặn mượn mới ngay từ ngày đầu. Đủ 7 ngày quá hạn được gắn trạng thái `SUSPENDED` để nhân viên theo dõi/escalate; nó không tạo một lần phạt hay chặn thứ hai. Gỡ `SUSPENDED` sau khi không còn loan quá hạn, số dư phạt đã trả/miễn, và hồ sơ liên quan đã đóng; gỡ có người/thời điểm lưu vết.
- Khoản phạt được ghi `ACCRUING` khi đang quá hạn, `DUE` khi loan trả/đóng; số dư bất kỳ lớn hơn 0 chặn mượn mới. Thanh toán một phần không gỡ chặn.
- Khi nhân viên tiếp nhận khai báo mất hợp lệ, dừng phạt và mở DamageCase. Khi quản lý xác nhận mất và chốt bồi thường, khoản phạt quá hạn chưa thanh toán của chính loan đó được miễn; phần đã thu được ghi có trừ vào khoản bồi thường. Nếu khai báo bị bác bỏ hoặc sách được trả lại, tính lại phạt đến ngày trả, trong giới hạn trần, sau khi cho độc giả phản hồi.

**Ví dụ tính:** Hạn trả ngày 10; sách trả ngày 11 và ngày 11 không phải ngày nghỉ/đóng cửa thì phạt 1.000 đồng. Nếu trả ngày 11 là ngày được loại trừ, phạt bằng 0 cho ngày đó. Nếu giá thay thế tham chiếu là 18.000 đồng thì trần phạt cuốn đó là 18.000 đồng; nếu giá chưa biết, trần tạm là 30.000 đồng. Khi khai báo mất được chấp nhận, khoản phạt chưa trả bị miễn và tiền phạt đã thu được trừ vào bồi thường của chính cuốn sách đó.

### 8. Sách hỏng/mất, định giá, phê duyệt và khiếu nại

- Quản lý thư viện phê duyệt/công bố biểu phí, tiêu chí phân loại và nguồn giá trước khi áp dụng. Thủ thư kiểm tra, lập hồ sơ, tính mức chuẩn theo biểu phí, thông báo căn cứ và cấp biên nhận; không tự đặt giá.
- `NORMAL_WEAR`: hao mòn thông thường, không thu. `MINOR_DAMAGE`: sửa được; thu chi phí sửa chữa có chứng từ, tối đa giá thay thế hiện hành. Nếu sửa đắt hơn thay sách hoặc ảnh hưởng lưu thông thì xếp `MAJOR_DAMAGE`.
- `MAJOR_DAMAGE`/`LOST`: ưu tiên bản cùng nhan đề và ấn bản hiện hành/tương đương, giá trị không thấp hơn; cộng phí xử lý đã công bố. Nếu không mua được bản tương đương, bồi thường 3 lần giá mua thay thế hiện hành cộng phí xử lý.
- Nếu sách hiếm, không bán, không có giá tin cậy hoặc hồ sơ tranh chấp, tạm chưa chốt khoản nợ; quản lý chọn nguồn định giá/báo giá, quyết định và lưu căn cứ. Hồ sơ chuẩn theo biểu phí không cần xin duyệt từng cuốn; ngoại lệ, miễn/giảm hoặc điều chỉnh bắt buộc quản lý duyệt.
- Nếu sách có bán nhưng không có giá niêm yết đáng tin cậy, thủ thư thu thập hai báo giá từ nguồn độc lập; quản lý chọn giá tham chiếu và ghi ngày/nguồn. Với tài liệu hiếm/không thể thay thế, quản lý quyết định trường hợp ngoại lệ, không tự áp công thức 3 lần.
- Ghi tình trạng lúc cấp và trả. Nếu bạn đọc báo hỏng có sẵn khi nhận, ghi cùng lượt mượn; không quy trách nhiệm nếu hồ sơ cấp phát đã ghi tình trạng đó. Hao mòn không thu.
- Khi có DamageCase, bản `DAMAGED`/`LOST` không được cấp. Trong lúc xác minh, chặn mượn mới và không cộng phạt trễ mới. Gửi thông báo qua tài khoản và email; thời hạn khiếu nại 5 ngày làm việc tính từ thông báo hiển thị thành công trong tài khoản. Nếu hệ thống thông báo lỗi, thời hạn chưa bắt đầu.
- Quản lý phản hồi khiếu nại trong 5 ngày làm việc; nếu cần điều tra thêm, thông báo lý do và ngày trả lời dự kiến. Hồ sơ tranh chấp chưa thu. Quyết định một phần/toàn bộ phải lưu căn cứ, người duyệt và lịch sử số tiền trước/sau.
- Hạn 5 ngày khiếu nại bắt đầu khi thông báo hiển thị trong tài khoản; email là bản nhắc. Nếu độc giả không phản hồi trước hạn, quyết định đã thông báo có hiệu lực; yêu cầu xem xét muộn chỉ nhận khi quản lý ghi nhận lý do chính đáng. Hồ sơ hư hỏng phải được mở trong lần kiểm tra lúc nhận hoặc cùng ca phục vụ; sau khi bản đã được chuyển `AVAILABLE`/cho mượn lại thì không quy lỗi cho lượt cũ nếu không có bằng chứng rõ ràng.
- Nếu sách được tìm thấy trước khi bồi thường hoàn tất, hủy phần bồi thường mất và kiểm tra tình trạng. Nếu tìm thấy sau khi đã trả tiền, hoàn/đối trừ tiền bồi thường sau khi khấu trừ chi phí thực tế có chứng từ; nếu đã nộp sách thay thế, sách thay thế thuộc thư viện và không hoàn lại chỉ vì tìm được sách cũ.
- Tiền phạt trễ và hư hỏng có thể cùng phát sinh nếu sách trả trễ nhưng vẫn còn; trường hợp mất thì áp dụng quy tắc miễn/đối trừ tiền phạt ở mục 7 để không thu hai lần cho cùng việc không có sách.

### 9. Thanh toán, điều chỉnh và chứng từ

- MVP không nhận thanh toán trực tuyến. Nhân viên chỉ ghi khoản đã thu khi tiền mặt/chuyển khoản ngoài hệ thống đã được xác nhận; không coi ảnh chụp giao dịch chưa đối soát là đã trả.
- Mỗi lần thu/miễn/điều chỉnh/hoàn là một dòng `FinePayment` có mã giao dịch, số tiền, loại giao dịch, thời gian, nhân viên, mã biên nhận và lý do. Không sửa/xóa dòng đã xác nhận; sai thì tạo dòng đảo/điều chỉnh có liên kết giao dịch gốc.
- Có thể thu một phần; số dư tính bằng tổng nợ trừ các khoản đã thu/miễn/điều chỉnh hợp lệ. Số dư dương chặn mượn. Nộp thừa tạo số dư có thể hoàn hoặc đối trừ với khoản khác sau khi quản lý xác nhận.
- Miễn/giảm/hoàn chỉ do quản lý duyệt, ghi lý do và căn cứ. Thủ thư bàn giao/đối soát cuối ca; cấp lại biên nhận thì đánh dấu bản sao, không tạo khoản thu mới.
- Bồi thường bằng sách thay thế được ghi là `IN_KIND_SETTLEMENT`; quản lý xác nhận sách đúng tiêu chí, thủ thư cấp biên nhận và đóng DamageCase. Không ghi như tiền mặt.

### 10. Thông báo, nhân viên và hệ thống lỗi

- Nhắc trước hạn 3 ngày, trong ngày đến hạn và mỗi 3 ngày quá hạn. Email lỗi không đổi hạn trả; trạng thái gửi/lỗi lưu lại, và thông tin hạn/nợ hiển thị trong tài khoản.
- Đặt chỗ sẵn gửi thông báo tài khoản + email. Nếu không có kênh hoạt động do lỗi hệ thống, giữ chỗ không hết hạn trong thời gian lỗi và gửi lại khi phục hồi.
- Người không dùng smartphone/email có thể kiểm tra trạng thái tại quầy sau khi xác thực thẻ; không nhận thông báo không tự gia hạn hạn trả.
- Quyền thủ thư: lập mượn/trả, xác nhận tình trạng, tính khoản chuẩn theo biểu phí, ghi thu và lập hồ sơ. Quyền quản lý: sửa biểu phí/lịch nghỉ, duyệt ngoại lệ/miễn giảm/định giá, sửa sai giao dịch và khóa/mở tài khoản. Mọi thao tác nhạy cảm ghi audit.
- Sửa lỗi phải lưu giá trị cũ/mới, lý do, người thao tác và người duyệt nếu cần. Không xóa lịch sử Loan, FinePayment, Reservation, ReturnReceipt hoặc DamageCase.
- Khi hệ thống ngừng, dùng phiếu tuần tự; khi nhập lại dùng mã giao dịch gốc/idempotency để không tạo mượn, trả hoặc tiền phạt trùng. Giao dịch dở dang phải hoàn tất toàn bộ hoặc không ghi gì.
- Mọi tính toán dùng ngày nghiệp vụ `Asia/Ho_Chi_Minh`; lưu timestamp UTC cùng ngày địa phương và phiên bản chính sách/lịch nghỉ. Dữ liệu báo cáo không lộ thông tin tài khoản cho người không có quyền.
- MVP vận hành tại một điểm phục vụ. Luân chuyển/cho trả tại chi nhánh khác, mượn liên thư viện và tài khoản khách nằm ngoài phạm vi.
- Khi chuyển dữ liệu cũ, đối soát tổng số đầu sách/bản vật lý/loan đang mở/nợ. Bản ghi thiếu mã, hạn, nhóm độc giả hoặc căn cứ tiền được gắn `MIGRATION_REVIEW`; không tự suy diễn ngày hạn hay tiền phạt. Giữ bản dữ liệu gốc và báo cáo số dòng đã nhập/bỏ/chờ xử lý.

### 11. Quyết định ngoài phạm vi MVP

Khách ngoài, mượn liên thư viện, tự mượn/self-check, thanh toán online, đặt trước khác ấn bản, gia hạn tự động ngày lễ và ghi thống kê đọc tại chỗ chưa hỗ trợ. Nếu phát sinh nhu cầu, tạo phiên bản quy định riêng trước khi triển khai; không xử lý bằng ngoại lệ không lưu vết.

### 12. Trạng thái chuẩn để hệ thống và nhân viên dùng thống nhất

- `Reader`: `ACTIVE`, `EXPIRED`, `SUSPENDED`, `MANUAL_BLOCK`. Khóa tự động do quá hạn bắt đầu từ ngày đầu; `SUSPENDED` là cờ escalation sau 7 ngày. `MANUAL_BLOCK` chỉ do quản lý đặt và ghi lý do.
- `BookCopy`: `AVAILABLE`, `ON_LOAN`, `ON_HOLD`, `RETURN_PENDING`, `RETURN_REVIEW`, `LONG_OVERDUE_REVIEW`, `MISSING`, `LOST_REVIEW`, `DAMAGED`, `LOST`, `WITHDRAWN`.
- `Loan`: `ACTIVE`, `RETURNED`, `LOST_REVIEW`, `CLOSED_LOST`. Loan quá hạn vẫn là `ACTIVE` kèm `overdue_since`; `LONG_OVERDUE_REVIEW` là cờ xử lý sau khi chạm trần, không tự đóng loan.
- `Reservation`: `PENDING`, `READY`, `FULFILLED`, `CANCELLED`, `EXPIRED`, `SKIPPED_INELIGIBLE`, `NOTIFIED_FAILED`.
- `Fine`: `ACCRUING`, `DUE`, `PARTIAL`, `PAID`, `WAIVED`, `CREDITED`. Tiền đã thu/hoàn/đối trừ lưu ở `FinePayment`, không xóa lịch sử Fine.
- `DamageCase`: `OPEN`, `INVESTIGATING`, `APPEALED`, `APPROVED`, `REJECTED`, `SETTLED`, `FOUND_AFTER_SETTLEMENT`.
- Thùng trả hợp lệ: Loan chuyển `RETURNED`; bản vật lý chuyển `RETURN_PENDING`. Khi bàn giao trực tiếp, Loan chuyển `RETURNED`; bản thành `AVAILABLE` sau kiểm tra hoặc `RETURN_REVIEW` nếu cần điều tra hư hỏng.

#### Chuẩn xử lý ngoại lệ còn lại

- Khi kiểm kê không tìm thấy bản, chuyển `MISSING` (không cấp mượn/không cấp reservation), mở hồ sơ kiểm tra và ghi lần kiểm kê, người kiểm tra, vị trí cuối cùng. Chỉ chuyển `LOST` sau khi quản lý xác nhận theo quy trình mất; tìm lại được thì đóng hồ sơ và chuyển `AVAILABLE` sau kiểm tra.
- Hao mòn thông thường gồm bạc màu/ố vàng do tuổi sách, gáy sờn nhẹ, vết bút chì tẩy sạch được và không ảnh hưởng đọc. Hỏng gồm rách/thiếu trang, bìa hoặc gáy bong ảnh hưởng sử dụng, bút mực không tẩy được, thấm nước/mốc, hoặc phụ kiện đi kèm bị mất. Đây là tiêu chí mặc định; biểu phí được duyệt phải có ảnh minh họa, mức thu và tiêu chí phân loại trước khi thu.
- Tranh chấp tiền phạt được tiếp nhận như một hồ sơ khiếu nại; giữ nguyên chứng từ và cách tính để đối chiếu. Phần đang tranh chấp tạm chưa thu và không dùng riêng phần đó làm lý do chặn mượn trong thời gian xem xét; khoản nợ không tranh chấp và các lượt quá hạn khác vẫn áp dụng điều kiện mượn bình thường. Quản lý trả lời trong 5 ngày làm việc, lưu phép tính và quyết định.
- Thông báo hoặc trạng thái không truy cập được do lỗi hệ thống không làm phát sinh hậu quả bất lợi dựa trên mốc thông báo đó: giữ reservation và tạm dừng thời hạn khiếu nại đến khi tài khoản truy cập lại; lưu thời điểm lỗi/phục hồi. Email lỗi đơn lẻ không dừng đồng hồ nếu thông tin vẫn hiển thị trong tài khoản.
- Trả hộ chỉ yêu cầu mã bản; không đọc tên, dư nợ, lịch sử hay thông tin liên hệ của chủ khoản mượn cho người trả hộ. Độc giả không có email/smartphone có thể xác thực tại quầy để xem hạn, nợ, reservation và nộp khiếu nại; áp dụng cùng thời hạn và cấp giấy xác nhận có ngày nhận.
- Khi nhập dữ liệu cũ, bản/loan/tiền thiếu căn cứ tiếp tục nằm trong `MIGRATION_REVIEW`, không đưa vào tồn kho sẵn có, không thu và không tự áp quy định mới cho giao dịch cũ. Quản lý đối chiếu hồ sơ gốc rồi mới xác nhận, điều chỉnh hoặc loại bỏ bằng bút toán có audit.
- Mỗi hồ sơ `RETURN_REVIEW`, `DamageCase` hoặc `MIGRATION_REVIEW` phải có người phụ trách, bước tiếp theo và ngày hẹn xem lại. Mặc định thủ thư phân công trong ca kế tiếp; quản lý rà soát hồ sơ tồn mỗi tuần và ghi lý do nếu chưa thể kết luận. Không tự động tính phí chỉ vì hồ sơ đang chờ.

### 13. Kịch bản kiểm tra bắt buộc trước khi đưa vào dùng

1. Mượn bản cuối đồng thời; vượt hạn mức đồng thời; gửi lặp do mạng chậm.
2. Hạn ngày bình thường, ngày đóng cửa, lễ/Tết, đóng cửa khẩn cấp; trả đúng 23:59 và sau 00:00.
3. Gia hạn ở hai ranh giới 48 giờ; queue phát sinh đồng thời; hạn mới rơi ngày đóng cửa.
4. FIFO khi độc giả đầu hàng hết hạn thẻ, còn nợ, quá quota, nhận email lỗi hoặc bỏ nhận.
5. Trả quầy lặp/mã sai, trả hộ, trả sách hỏng; thùng đúng hạn, sai mã, không có sách, nhân viên chậm, QR lỗi/phiếu giấy.
6. Tính nhiều cuốn quá hạn qua ngày nghỉ; chạm trần; khai mất hợp lệ/bị bác; sách tìm lại trước/sau khi bồi thường.
7. Thanh toán đủ/một phần/nộp thừa, hoàn tiền, miễn giảm, giao dịch sai và đảo giao dịch.
8. Thẻ hết hạn/đổi nhóm; hồ sơ trùng; nhân viên sửa sai; kiểm kê phát hiện bản mất.

---

## Phụ lục B — Rà soát tình huống thực tế và phương án xử lý

Tài liệu này lưu lại checklist rà soát ban đầu. Các câu hỏi bên dưới được viết trước khi chốt phương án; câu trả lời/quy tắc đang đề xuất được tập hợp tại Phụ lục A, là nguồn duy nhất cho đặc tả MVP. Checklist này dùng để đối chiếu và kiểm tra tình huống, không phải nguồn quy định riêng.

### 1. Các điểm cần quyết định trước khi viết chức năng

| Mã | Tình huống / rủi ro | Câu hỏi cần chốt | Gợi ý xử lý |
|---|---|---|---|
| P0-1 | Một lượt mượn vừa quá hạn 1 ngày thì điều kiện mượn đã chặn sách mới; đến ngày thứ 7 lại chuyển tài khoản `SUSPENDED`. | `SUSPENDED` có tác dụng gì thêm so với chặn mượn? Trạng thái này được gỡ tự động hay cần nhân viên? | Đã xử lý trong bản cập nhật: chặn mượn từ ngày đầu; ngày thứ 7 là trạng thái escalation theo dõi, không tạo một lệnh chặn/phạt thứ hai; gỡ sau khi trả, xử lý nợ và đóng hồ sơ. |
| P0-2 | Độc giả báo mất sách sau nhiều ngày quá hạn. Phạt dừng tại lúc khai báo mất, nhưng khoản phạt đã tích lũy có thể cộng với tiền bồi thường. | Khoản phạt trước ngày báo mất có tiếp tục phải thu cùng tiền bồi thường không? | Đã xử lý: chỉ khai báo có mã hồ sơ do nhân viên tiếp nhận mới dừng phạt; khi xác nhận mất, miễn phần phạt chưa thu và ghi có khoản đã thu để trừ vào bồi thường. Nếu báo mất bị bác bỏ, tính lại phạt đến khi trả, theo mức trần. |
| P0-3 | Thùng trả ghi giờ khai báo để dừng tiền phạt nhưng hạn mức trước đây chỉ được giải phóng sau khi nhân viên kiểm tra. | Trong lúc chờ xác nhận, loan/quota và bản sách ở trạng thái nào? | Đã xử lý: biên nhận hợp lệ đóng loan và giải phóng quota ngay; dừng phạt theo giờ khai báo; copy ở `RETURN_PENDING` và chưa sẵn sàng cho mượn đến khi kiểm tra. |
| P0-4 | Phạt không có trần, có thể tăng lâu dài; khoản bồi thường có thể cộng thêm. | Có trần theo từng cuốn hay không? | Đã đề xuất trần 30.000 đồng/cuốn hoặc giá thay thế thấp hơn. Khi chạm trần, chuyển theo dõi quá hạn dài; nếu xác nhận mất, tiền phạt được miễn/đối trừ theo P0-2. |
| P0-5 | Quy tắc nêu gia hạn trong “2 ngày trước hạn”, trả đúng đến 23:59, nhưng hệ thống dùng thời điểm và ngày địa phương khác nhau. | “2 ngày” là 48 giờ hay hai ngày lịch? | Đã xử lý: cửa sổ gia hạn bắt đầu đúng 48 giờ trước `due_at`, kết thúc tại hạn hiện tại, theo `Asia/Ho_Chi_Minh`; hạn mới thêm 7 ngày lịch và dời nếu rơi vào ngày thư viện đóng cả ngày. |
| P0-6 | Phạt loại trừ ngày lễ/Tết và ngày thư viện đóng cửa cả ngày; lịch có thể thay đổi. | Ngày nghỉ nào là nguồn chuẩn? Đóng cửa một phần hay khẩn cấp xử lý sao? | Đã xử lý: dùng lịch nghỉ chính thức và lịch thư viện có hiệu lực; ngày đóng cả ngày được miễn, đóng một phần vẫn tính. Đóng khẩn cấp được miễn cho ngày đóng; quản lý có thể dời hạn hàng loạt và lưu quyết định. |
| P0-7 | Công thức bồi thường sách mất/hỏng nặng cần giá thay thế; sách hiếm/không bán có thể không định giá được. | Nguồn giá, ngày định giá, báo giá và người duyệt? | Đã xử lý: thu hai báo giá độc lập nếu không có giá tin cậy; quản lý chọn nguồn/giá và duyệt ngoại lệ có căn cứ. |

### 2. Đăng ký độc giả và điều kiện đủ quyền mượn

- **Thẻ/hồ sơ hết hạn trong lúc đang mượn:** độc giả có được gia hạn, trả sách, thanh toán không? Hạn trả sách có thay đổi không? Nên luôn cho phép trả/đóng nợ dù tài khoản hết hạn.
- **Tốt nghiệp, nghỉ việc, bảo lưu, chuyển cơ sở:** chặn mượn từ thời điểm nào; xử lý lượt đang mượn, đặt trước và phạt còn nợ ra sao?
- **Đổi loại độc giả:** sinh viên thành giảng viên/nhân viên hoặc ngược lại khi đang giữ sách; hạn mức mới áp dụng ngay hay sau khi trả hết lượt hiện tại?
- **Một người có nhiều hồ sơ/tài khoản, đổi mã số, mất thẻ hoặc cấp thẻ mới:** làm sao tránh lách hạn mức/nợ bằng hồ sơ mới? Mã cũ được giữ liên kết lịch sử thế nào?
- **Độc giả mượn hộ/đưa thẻ cho người khác:** ai chịu trách nhiệm giao dịch; thủ thư cần xác minh danh tính bằng gì? Không lưu ảnh giấy tờ nếu không cần thiết.
- **Khách ngoài, độc giả liên thư viện, cựu sinh viên:** có được đăng ký không? Nếu MVP chưa hỗ trợ thì từ chối rõ tại bước đăng ký, không gán nhầm nhóm.
- **Tài khoản bị khóa thủ công vì lý do khác:** ai có quyền khóa/mở; bắt buộc nhập lý do và thời điểm hiệu lực; xử lý yêu cầu gia hạn/đặt trước đang chờ như thế nào?
- **Độc giả có nợ chưa đến hạn, nợ đang khiếu nại, được miễn một phần hoặc đã thanh toán một phần:** định nghĩa cụ thể trạng thái nào chặn mượn. Theo quy tắc hiện tại, chỉ cần còn số dư phạt là bị chặn; khoản tranh chấp cũng tạm chặn.

### 3. Tài liệu, bản sách và khả năng cho mượn

- **Một nhan đề có nhiều ấn bản/ngôn ngữ/định dạng:** hàng chờ đặt theo nhan đề hay đúng ấn bản? Người đặt có chấp nhận ấn bản khác không?
- **Sách nhiều tập/bộ, phụ lục, CD hoặc tài liệu đi kèm:** tính mỗi tập/phần là một bản và một suất hạn mức hay cả bộ là một lượt? Mất một tập thì bồi thường thế nào?
- **Sách giáo trình và tài liệu tham khảo:** có thể mượn theo kỳ hạn/hạn mức riêng; nếu cùng nhan đề có một bản chỉ đọc tại chỗ và bản khác cho mượn về, chính sách áp ở cấp nhan đề hay bản vật lý?
- **Bản bị hỏng, đang phục chế, thất lạc khỏi kệ, đang kiểm kê hoặc dành cho lớp học:** không được tính là “còn sẵn” và không được cấp mượn/đặt trước.
- **Tổng bản sách giảm hoặc tăng:** quy trình thêm bản, thanh lý, nhập lại bản thay thế; đảm bảo `available_copies` không sai lệch với các `BookCopy`.
- **Mã vạch mất, trùng, bong hoặc quét không nhận:** cách xác minh thủ công và ghi nhận người xác nhận; không cho phép tạo hai bản cùng mã.
- **Giá thay thế cũ hoặc không có giá:** ai cập nhật giá tham chiếu, nguồn và ngày cập nhật; giá tham chiếu không tự động trở thành khoản phải thu nếu chưa theo biểu phí.

### 4. Lập lượt mượn, hạn mức và giao dịch đồng thời

- **Mượn nhiều cuốn một lần nhưng một cuốn không đủ điều kiện:** toàn bộ giao dịch hủy hay các cuốn hợp lệ vẫn được mượn? Hiển thị lý do từ chối theo từng mã.
- **Độc giả chạm đúng hạn mức:** đặt trước/giữ sách sẵn sàng có chiếm hạn mức trước khi mượn không? Gợi ý: hạn mức chỉ tăng khi lập lượt mượn, nhưng giữ chỗ có thời hạn riêng.
- **Hai độc giả cùng lúc yêu cầu bản cuối cùng:** chỉ một người nhận được bản; lượt còn lại nhận thông báo/được vào hàng chờ. Cần cập nhật kho trong một giao dịch để không cấp trùng.
- **Hai nhân viên quét cùng một mã gần đồng thời:** thao tác thứ hai phải báo bản đã được mượn/trả, không tạo giao dịch trùng.
- **Bấm nút mượn/submit hai lần, mạng chậm hoặc tải lại trang:** không được tạo hai lượt mượn hay hai khoản phạt. Giao dịch cần khóa/idempotency.
- **Một độc giả gửi đồng thời hai yêu cầu khác nhau làm vượt hạn mức:** hệ thống phải kiểm tra tổng lượt còn hiệu lực trong cùng giao dịch.
- **Máy/DB ngắt giữa lúc quét thẻ, trừ tồn kho và tạo loan:** hoặc hoàn tất toàn bộ hoặc hoàn tác toàn bộ; nhân viên cần tìm được giao dịch nào đã thực sự hoàn tất.
- **Trả từng cuốn trong một nhóm mượn:** vì mỗi `Loan` là một bản, đóng/phạt/tính hạn mức từng bản riêng, không chờ cả nhóm trả xong.

### 5. Gia hạn

- **Yêu cầu đúng ranh giới cửa sổ gia hạn:** chốt giờ bắt đầu/kết thúc hai ngày cuối, dùng giờ địa phương; tránh trường hợp người dùng thấy “còn 2 ngày” nhưng hệ thống từ chối.
- **Hạn trả đã được dời vì ngày đóng cửa:** cửa sổ hai ngày tính theo hạn mới, không theo hạn ban đầu.
- **Người khác đặt trước cùng lúc gia hạn:** thao tác nào được ghi trước; cần khóa giao dịch để không vừa gia hạn vừa cấp quyền giữ bản cho hàng chờ.
- **Có đặt trước nhưng yêu cầu bị hủy/độc giả đầu hàng không đủ điều kiện:** có cho gia hạn ngay không? Hàng chờ đang chờ xử lý có được coi là có người đặt?
- **Một lượt đã gia hạn nhưng nhân viên sửa hạn thủ công hoặc thư viện đóng cửa:** thay đổi nào được phép, ai duyệt, có tiêu thụ lượt gia hạn không?
- **Gia hạn bị từ chối:** thông báo lý do và hạn trả hiện tại; không sửa hạn, không tạo khoản phạt chỉ vì yêu cầu bị từ chối.
- **Sách không được phép gia hạn theo loại tài liệu hoặc người mượn:** phải kiểm tra chính sách của cả nhóm độc giả lẫn loại tài liệu.
- **Gia hạn trực tiếp tại quầy so với trên web:** có cùng điều kiện, cùng lưu người thực hiện/thời điểm và cùng lịch sử không?

### 6. Đặt trước và hàng chờ

- **Có một bản còn sẵn nhưng đang `RETURN_REVIEW`, `DAMAGED`, `LOST` hoặc chỉ đọc tại chỗ:** xác định có được đặt trước; không tính bản không đủ điều kiện là bản sẵn.
- **Nhiều độc giả đặt cùng lúc:** FIFO theo timestamp máy chủ; nếu timestamp bằng nhau thì cần khóa phụ ổn định (ví dụ mã yêu cầu).
- **Người đầu hàng đã đủ hạn mức, có nợ, tài khoản hết hạn hoặc bị khóa:** bỏ lượt, giữ lại đến khi đủ điều kiện, hay hỏi độc giả? Chính sách hiện nói chuyển sang người đủ điều kiện tiếp theo; cần định nghĩa có mất lượt hay không.
- **Người đầu hàng không nhận trong 48 giờ, không đọc được email, email lỗi hoặc thư vào spam:** thời gian giữ tính từ lúc tạo thông báo hay gửi thành công? Có thông báo qua tài khoản/app không?
- **48 giờ đi qua cuối tuần, lễ hoặc kỳ nghỉ dài:** quy tắc hiện chỉ gia hạn nếu hạn kết thúc khi thư viện đóng; cần quyết định có cộng toàn bộ giờ đóng cửa hay chỉ chuyển đến lần mở cửa kế tiếp.
- **Độc giả hủy yêu cầu, đổi ý, không đến nhận hoặc muốn đặt lại:** giữ lịch sử trạng thái; có giới hạn số yêu cầu đang chờ hoặc số lần bỏ nhận không?
- **Nhiều bản của cùng nhan đề được trả cùng lúc:** hệ thống cấp lần lượt cho queue, không gửi nhiều thông báo giữ cùng một bản.
- **Không còn bản nào được mượn về (đã thanh lý/hỏng):** hàng chờ phải được thông báo/hủy, không để yêu cầu treo vô thời hạn.
- **Đặt trước vào bản khác ấn bản hoặc nhiều nhan đề trùng tên:** hiển thị rõ nhan đề, tác giả, ấn bản và điều kiện thay thế.
- **Lỗi gửi thông báo:** thời gian 48 giờ có bắt đầu không; ai xử lý địa chỉ lỗi; cần ghi lý do chuyển sang người tiếp theo.

### 7. Trả tại quầy và trả ngoài giờ

- **Người khác mang sách đến trả hộ:** cho trả theo mã bản mà không cần chủ tài khoản có mặt; không cho người trả hộ xem nợ/thông tin riêng của chủ tài khoản.
- **Quét nhầm bản, bản không nằm trong lượt mượn, hoặc lượt đã được trả:** thao tác phải dừng hoặc báo đã trả; không tạo trả lần hai/âm kho.
- **Sách trả đúng hạn nhưng hỏng/mất trang:** ghi ngày trả để dừng phạt; chuyển bản sang `RETURN_REVIEW`/`DAMAGED`; khoản bồi thường xử lý riêng.
- **Nhân viên đánh dấu trả nhưng sách chưa được kiểm tra:** bản có sẵn cho người khác không? Gợi ý: chưa; chỉ chuyển `AVAILABLE` sau kiểm tra sơ bộ.
- **Thùng trả đầy, sách bị kẹt/ướt/mất, người dùng không nhận email, hoặc QR/Internet hỏng:** phiếu giấy dùng thế nào, ai cấp mã, cách đối chiếu timestamp và xử lý thiếu bằng chứng?
- **Biên nhận khai một mã nhưng bên trong là sách khác/không có sách:** khi nào được coi là khai báo hợp lệ; ai kết luận sai mã; phạt dừng hay tiếp tục trong lúc điều tra?
- **Độc giả bỏ sách vào thùng đúng hạn nhưng nhân viên mở sau nhiều ca/ngày nghỉ:** quy định hiện dừng phạt theo giờ khai hợp lệ nhưng chưa nêu rõ hạn tối đa kiểm tra; cần deadline và đường escalte.
- **Sách bị hỏng trong thùng sau khi đã bỏ vào:** xác định tình trạng khi thả bằng cách nào, trách nhiệm bảo quản thuộc ai, quy trình khiếu nại ra sao.
- **Thùng nhận tài liệu quá hạn/hỏng/khổ lớn:** hiện không nhận; cần biển hướng dẫn và cách xử lý nếu độc giả vẫn bỏ vào thùng.
- **Trả ngoài giờ xong nhưng lượt mượn còn chiếm quota:** nêu rõ người dùng thấy trạng thái `DROP_REPORTED` và thời điểm giải phóng quota; tránh hiểu nhầm là đã trả hoàn tất.

### 8. Ngày đến hạn, tiền phạt và khóa tài khoản

- **Tính ngày quá hạn:** chốt ví dụ cho trả đúng 23:59, 00:00 ngày kế tiếp, trả ngày lễ và trả ngày thư viện đóng; hiện “ngày sau hạn” và “từ 00:00 sau ngày đến hạn” cần nhất quán.
- **Ngày nghỉ cập nhật sau khi đã phát sinh khoản phạt:** có tính lại tự động không? Lưu lịch phiên bản lịch nghỉ để giải thích lịch sử.
- **Thư viện đóng nửa ngày, đóng khẩn cấp hoặc thay đổi giờ hoạt động:** chính sách hiện chỉ nói đóng cả ngày. Chốt phạm vi miễn phạt và có dời hạn trả hay không.
- **Sách được gia hạn:** khoản phạt dựa theo hạn mới; tránh tính theo hạn cũ trong tác vụ hằng ngày.
- **Độc giả trả ngoài giờ hợp lệ:** dùng ngày khai báo làm mốc, nhưng biên nhận thiếu/mã bản sai thì xử lý ra sao.
- **Nhiều cuốn quá hạn cùng lúc:** mỗi `Loan` tính riêng 1.000đ/ngày; hiển thị từng cuốn, số ngày, ngày nghỉ được loại và tổng cộng để độc giả kiểm tra.
- **Tác vụ chạy lặp, trễ hoặc lỗi:** không tạo phí hai lần/ngày, không bỏ ngày; có thể tính lại từ dữ liệu ngày bắt đầu/kết thúc và quy tắc đã chụp.
- **Khoản phạt phát sinh hằng ngày nhưng chưa trả:** xác định khi nào khoản được ghi vào sổ, ngày đến hạn thanh toán, nợ một phần, miễn một phần và số dư.
- **Không trần tiền phạt:** nếu tiền vượt giá sách hoặc vượt 200.000 đồng, áp dụng quyền xin giảm nào? Ai thông báo và quyết định?
- **Mốc `SUSPENDED` 7 ngày:** tính 7 ngày lịch hay 7 ngày được tính phạt? Ai gỡ trạng thái, có tự gỡ sau khi trả sách nhưng còn nợ tiền không?
- **Độc giả có nhiều lượt quá hạn:** trả một cuốn có gỡ khóa không nếu cuốn khác còn quá hạn? Quy tắc hiện yêu cầu không còn lượt quá hạn và không còn nợ, nên cần thể hiện trạng thái từng điều kiện.
- **Độc giả trả sách nhưng không thanh toán phí:** khoản mượn đóng, nhưng tài khoản tiếp tục bị chặn; nêu rõ thông báo và cách thanh toán/kiến nghị.
- **Tranh chấp khoản phạt:** có dừng thu/khóa mượn không? Quy tắc hiện chỉ nói khiếu nại bồi thường, chưa nói khiếu nại tiền phạt trễ.

### 9. Sách mất, hỏng, định giá và khiếu nại

- **Hao mòn tự nhiên hay hư hỏng:** ví dụ cụ thể cho gáy sờn, giấy ngả màu, bút chì tẩy được, bút mực, nước, mốc, rách, thiếu trang, mất bìa; tránh nhân viên áp dụng khác nhau.
- **Tình trạng đã hỏng trước khi mượn nhưng không được ghi nhận:** ảnh/biên bản khi cấp sách có bắt buộc không? Thiếu bằng chứng thì ai chịu trách nhiệm chứng minh?
- **Hư nhẹ có thể sửa nhưng giá sửa cao hơn thay mới:** áp dụng mức thấp hơn hay chuyển thành `MAJOR_DAMAGE`? Mức tối đa là giá mua mới hay giá thay thế tham chiếu?
- **Không mua được sách, giá niêm yết cũ, sách ngoại văn/đã ngừng xuất bản:** dùng bao nhiêu báo giá, nguồn nào, báo giá gồm những khoản gì, ai phê duyệt?
- **Thay thế bằng ấn bản mới hơn/tương đương:** tiêu chí tương đương gồm nhan đề, tác giả, nội dung, ngôn ngữ, nhà xuất bản, bìa và giá trị; ai chấp nhận cuốn thay?
- **Tài liệu quý/hiếm/luận văn không thể mua lại:** quy trình ngoại lệ do quản lý quyết định; có chuyên gia/thư viện khác định giá không?
- **Mất một tập trong bộ hoặc phụ lục đi kèm:** tính giá trị một tập, cả bộ, hay chi phí hoàn thiện bộ? Trường hợp chỉ có thể mua cả bộ cần tiêu chí.
- **Báo mất nhưng sau đó tìm được:** nếu chưa bồi thường thì đóng hồ sơ; nếu đã trả tiền hoặc nộp sách thay thế thì hoàn/đối trừ thế nào, ai chịu chi phí đã phát sinh?
- **Độc giả không đồng ý kết luận hư hỏng:** thời hạn 5 ngày tính từ lúc gửi hay lúc xác nhận nhận thông báo; email không đến thì sao; ai xem xét cấp hai?
- **Không phản hồi khiếu nại trong 5 ngày:** hồ sơ tự thành khoản phải thu hay cần thông báo nhắc/hạn cuối rõ ràng?
- **Khiếu nại được chấp nhận một phần:** sửa khoản phải thu, hoàn tiền/đối trừ, mở khóa và lưu vết thế nào?
- **Tình trạng sách phát hiện sau khi đóng lượt trả:** thời hạn tối đa để lập `DamageCase`; cần bằng chứng liên tục từ lúc nhận để tránh quy trách nhiệm tùy tiện.
- **Cộng tiền phạt trễ với bồi thường:** quy định hiện tách hai khoản nhưng chưa nêu việc thu cả hai; cần nêu ví dụ và công thức để tránh phạt trùng khi sách mất.

### 10. Thu tiền, miễn giảm và biên nhận

- **Thanh toán một phần:** số dư còn lại có chặn mượn không? Quy tắc hiện có hỗ trợ thanh toán từng phần nhưng điều kiện mượn chặn khi còn bất kỳ số dư.
- **Nộp thừa, thu nhầm, giao dịch bị hủy hoặc hoàn tiền:** ai duyệt, chứng từ nào, có bù trừ sang khoản khác không?
- **Thu tiền mặt cuối ca:** bàn giao, đối chiếu với `FinePayment`, xử lý chênh lệch; nếu MVP chưa quản lý tiền mặt thì hệ thống chỉ ghi nhận chứng từ hay ghi tiền thực thu?
- **Miễn/giảm:** mức nào nhân viên có thể nhập theo quyết định, trường hợp nào cần quản lý; phải lưu số tiền trước/sau, lý do, người duyệt và ngày.
- **Mất biên nhận hoặc cần in lại:** mã giao dịch duy nhất, đánh dấu bản in lại, không tạo thêm khoản thu.
- **Biểu phí thay đổi:** áp mức mới từ ngày hiệu lực nào; khoản đã phát sinh giữ mức cũ hay tính lại? `Fine` cần chụp mức và phiên bản chính sách lúc áp dụng.
- **Bồi thường bằng sách thay thế thay vì tiền:** có khoản phí xử lý riêng không, lúc nào ghi đã hoàn tất, xử lý sách thay thế nếu không đúng tiêu chí.

### 11. Thông báo và trải nghiệm độc giả

- **Email sai, hộp thư đầy, không có email hoặc thông báo vào spam:** độc giả vẫn chịu hạn; cần hiển thị hạn và khoản nợ trong trang tài khoản, cập nhật email và lưu trạng thái gửi.
- **Thông báo đặt sách sẵn bị lỗi:** mốc 48 giờ tính từ lúc nào và có gia hạn khi lỗi do hệ thống không?
- **Không gửi được email nhắc hạn:** không được tự dời hạn; cần hàng đợi gửi lại/log lỗi và kênh thông báo thay thế ở quầy/tài khoản.
- **Độc giả không đồng ý với số ngày phạt:** màn hình/biên nhận cần có hạn gốc, hạn sau gia hạn/dời ngày, ngày nghỉ bị loại, ngày trả dùng để tính và phép tính theo từng cuốn.
- **Độc giả khuyết tật, không dùng email, không có smartphone:** có thể nhận thông báo/đặt chỗ bằng tài khoản web hoặc qua quầy không?

### 12. Nhân viên, phân quyền và sửa sai

- **Nhân viên thao tác nhầm mượn/trả, ngày hạn, mức phạt hoặc loại tài liệu:** ai được sửa; phải lưu giá trị cũ/mới, lý do và người duyệt; không xóa dấu vết.
- **Thủ thư tự miễn tiền hoặc tự chỉnh giá thay thế:** phân quyền hệ thống phải ngăn thao tác ngoài thẩm quyền; ngoại lệ cần thông tin người duyệt.
- **Nhân viên nghỉ việc/chuyển quyền:** giao dịch cũ vẫn gắn với nhân viên đã thực hiện; tài khoản không còn đăng nhập nhưng lịch sử còn.
- **Giao dịch ngoại tuyến/phiếu giấy:** mã phiếu duy nhất, đồng bộ chống nhập trùng, thứ tự thời gian và người nhập lại.
- **Bất đồng giữa nhân viên hai ca:** trạng thái hồ sơ và bước tiếp theo phải rõ; không để `RETURN_REVIEW` hoặc `DamageCase` treo vô hạn.
- **Khẩn cấp (thư viện đóng cửa, thiên tai, dịch vụ ngừng):** ai có quyền gia hạn hàng loạt/miễn phí, phạm vi độc giả nào, cần ghi nhận quyết định và ngày hiệu lực.

### 13. Dữ liệu và trạng thái hệ thống

- **Chuyển dữ liệu sách:** tổng số bản, bản còn, bản đang mượn, mã vạch trùng/thiếu; cần đối soát trước khi lấy `BookCopy` làm nguồn tồn kho.
- **Chuyển độc giả và nợ cũ:** mã trùng, người đã tốt nghiệp, hạn trả thiếu, khoản phạt không có căn cứ/biên nhận; quyết định giữ, bỏ hay cần duyệt từng dữ liệu lỗi.
- **Chuyển lượt mượn đang mở:** nếu ngày đến hạn/loại độc giả thiếu, dùng quy tắc nào; không tự gán ngày hoặc phí mà không ghi nguồn.
- **Sửa dữ liệu tồn kho sau kiểm kê:** nếu hệ thống báo sách sẵn nhưng không tìm thấy, trạng thái `MISSING`/`INVESTIGATION` nào chặn cấp mới và đặt trước?
- **Xóa/đổi nhan đề hoặc gộp bản trùng:** lịch sử Loan/Reservation/Fine vẫn phải giữ đúng nhan đề và bản lúc giao dịch.
- **Hệ thống downtime:** nhân viên ghi giao dịch thủ công; khi nhập lại cần tránh cấp lại cùng bản hoặc tính phạt trùng.
- **Thời gian máy chủ sai/khác múi giờ:** tất cả hạn trả/biên nhận dùng múi giờ nghiệp vụ; lưu timestamp UTC và ngày địa phương để có thể tính lại.

### 14. Bộ tình huống nghiệm thu nên chạy trước khi mở dùng

1. Mượn cuốn cuối cùng đồng thời bởi hai độc giả; chỉ một lượt thành công.
2. Hai thao tác đồng thời khiến một độc giả chạm/vượt hạn mức; hệ thống không vượt hạn.
3. Trả đúng hạn lúc 23:59, sau hạn lúc 00:00, ngày lễ, ngày thư viện đóng cửa và ngày đóng cửa khẩn cấp.
4. Gia hạn đúng đầu/cuối cửa sổ 2 ngày; đặt trước phát sinh cùng lúc; hạn được dời vì ngày đóng cửa.
5. FIFO với người đầu hàng hết hạn thẻ, quá hạn sách, còn nợ, không nhận email, hủy hoặc bỏ nhận.
6. Trả ở quầy, trả lặp mã, quét nhầm mã, người khác trả hộ, sách hỏng khi trả.
7. Trả thùng đúng hạn; thiếu sách/sai mã; biên nhận hợp lệ nhưng nhân viên chậm kiểm tra; QR lỗi và dùng phiếu giấy.
8. Tính nhiều khoản phạt qua ngày nghỉ; chạy tác vụ tính phí lặp; thanh toán một phần; miễn một phần; hoàn/điều chỉnh.
9. Báo mất khi chưa quá hạn, sau khi quá hạn, tìm lại trước bồi thường và tìm lại sau bồi thường.
10. Hư nhẹ, hỏng nặng, hao mòn tự nhiên, sách đã hỏng trước khi mượn, sách hiếm/không định giá được, khiếu nại trong hạn và sau hạn.
11. Thẻ hết hạn hoặc loại độc giả đổi trong lúc đang mượn; tài khoản bị khóa/gỡ khóa; còn phạt nhưng đã trả hết sách.
12. Nhân viên sửa sai, thu tiền nhầm, nhập giao dịch ngoại tuyến, và đối soát bản sách sau kiểm kê.

### 15. Đối chiếu checklist với bản quy định cập nhật

Các tình huống dưới đây đã có phương án mặc định trong Phụ lục A. Các mức mới là đề xuất cập nhật cho MVP, chưa nên coi là đã được nhóm/ban quản lý phê duyệt cho vận hành.

| Nhóm tình huống trong checklist | Phương án mặc định ở bản cập nhật |
|---|---|
| P0: trạng thái quá hạn/khóa | Chặn mượn ngay ngày đầu quá hạn; sau 7 ngày gắn `SUSPENDED` để theo dõi, không tính thành lệnh chặn/phạt thứ hai; gỡ khi sách, nợ và hồ sơ đã được xử lý. |
| P0: khai báo mất và tiền phạt | Khai báo do nhân viên tiếp nhận có mã hồ sơ mới dừng phạt; khi xác nhận mất, miễn phạt chưa thu và ghi có khoản đã thu để trừ vào bồi thường. Nếu khai báo bị bác hoặc sách trả lại thì tính lại đến ngày trả. |
| P0: thùng trả | Biên nhận hợp lệ đóng loan, giải phóng quota và dừng phạt ngay; copy ở `RETURN_PENDING`, không cho mượn đến khi kiểm tra. Phiếu giấy có mã tuần tự khi hệ thống ngừng. |
| P0: trần phạt | Đề xuất trần 30.000đ/bản hoặc giá thay thế thấp hơn; chạm trần chuyển `LONG_OVERDUE_REVIEW`, không tự kết luận mất. |
| P0: gia hạn/ngày giờ | Cửa sổ đúng 48 giờ trước hạn; +7 ngày lịch; ngày đến hạn/đóng cửa xử lý theo lịch địa phương và lịch thư viện. |
| P0: giá bồi thường | Giá biểu phí do quản lý duyệt trước; sách không có giá tin cậy cần hai báo giá độc lập và phê duyệt ngoại lệ. |
| Đăng ký, nhóm độc giả, hồ sơ trùng/khách ngoài | Hồ sơ độc giả duy nhất; SV/GV/nhân viên có hiệu lực ngày bắt đầu/kết thúc; không phục vụ khách ngoài trong MVP; đổi nhóm không viết lại các loan cũ. |
| Loại tài liệu, bản sách và mượn đồng thời | Tồn kho theo `BookCopy`; không cấp bản không sẵn sàng; giao dịch mượn/quota nguyên tử; loan theo từng bản. |
| Gia hạn và đặt trước | Một lần gia hạn cùng điều kiện ở quầy/web; FIFO theo timestamp/mã yêu cầu; giữ 48h từ lúc thông báo hiển thị, kéo đến giờ phục vụ kế tiếp nếu thư viện đóng. |
| Trả tại quầy/thùng và sách hỏng khi nhận | Trả hộ được nhưng không lộ thông tin; quét lặp không đóng loan hai lần; sách hỏng đi `RETURN_REVIEW`; nhận thùng đủ điều kiện là mốc thư viện nhận quyền kiểm soát. |
| Lịch nghỉ, tiền phạt, thanh toán, miễn/giảm | Phạt 1.000đ/cuốn/ngày tính riêng từng `Loan`, loại ngày lễ/Tết/đóng cả ngày; khoản dư chặn mượn; thu/hoàn/miễn có sổ giao dịch và biên nhận, miễn giảm do quản lý duyệt. |
| Mất/hỏng, báo giá, khiếu nại, tìm thấy lại | Phân loại, giữ bằng chứng, áp biểu phí đã duyệt; ngoại lệ do quản lý; 5 ngày làm việc để khiếu nại; sách tìm lại thì hủy/đối trừ theo trạng thái bồi thường. |
| Email lỗi, quyền nhân viên, sửa sai, outage và chuyển dữ liệu | Tài khoản là nguồn thông báo chính, lỗi email không dời hạn; quyền theo vai trò; sửa sai có audit; phiếu giấy chống trùng; dữ liệu thiếu khi chuyển được đưa vào `MIGRATION_REVIEW`, không tự suy diễn.

Các quyết định mới cần người có thẩm quyền xác nhận trước khi kích hoạt gồm trần phạt, biểu phí sửa chữa/xử lý, lịch/người trực thùng trả và biểu phí bồi thường. Những tình huống nghiệm thu ở mục 14 là cách kiểm tra các lựa chọn này đã được triển khai nhất quán.

#### Trạng thái và việc còn phải phê duyệt

- Các vấn đề nghiệp vụ P0/P1 trong checklist đã có phương án mặc định ở bản quy định cập nhật; nhóm có thể dùng mục 14 để kiểm tra việc triển khai.
- Trước khi áp dụng thực tế, quản lý thư viện cần duyệt/công bố biểu phí hỏng/mất và nguồn giá, trần phạt đề xuất 30.000 đồng/bản (hoặc giá thay thế thấp hơn), lịch nghỉ chính thức, điểm nhận/lịch lấy và người chịu trách nhiệm thùng trả, cùng thời hạn/phân quyền khiếu nại.
- Đây là các quyết định quản trị cần ký duyệt/công bố, không phải câu hỏi nghiệp vụ còn bỏ ngỏ trong đặc tả. Nếu quản lý chọn giá trị khác, cập nhật bản quy định chuẩn và ngày hiệu lực trước khi đưa vào dùng; lưu phiên bản cũ để giải thích giao dịch phát sinh trước đó.
- **P2 — Có thể để sau MVP:** thông báo nhiều kênh, khách ngoài/thẻ liên thư viện, mượn liên chi nhánh, thanh toán online, lịch sử đọc tại chỗ.

---

## Phụ lục C — Đối chiếu với quy định thư viện tại TP.HCM

**Ngày rà soát:** 01/11/2026
**Phạm vi:** Đối chiếu bộ quy định của MVP đã được nhóm chốt với quy định công khai của một số thư viện ở TP.HCM. Quy định của từng nơi phục vụ nhóm độc giả, loại tài liệu, thẻ/gói dịch vụ và quy trình riêng; số liệu dưới đây dùng để tham khảo, không mặc nhiên áp dụng cho dự án.

Phần phân tích thiếu sót dưới đây ghi nhận bộ quy tắc nền trước khi cập nhật theo yêu cầu tiếp theo. Các khắc phục đã được đưa vào Phụ lục A; phần cuối tài liệu liệt kê những điểm cần quản lý thư viện duyệt hoặc vận hành thực tế.

Bản đặc tả tác nghiệp mới nhất là Phụ lục A; các ngưỡng cập nhật (gồm trần phạt đề xuất) là lựa chọn cho MVP, không phải quy định được các thư viện tham khảo đồng loạt áp dụng.

### 1. Tóm tắt chính sách của nhóm

- Sinh viên: tối đa 5 bản, 14 ngày; giảng viên/nhân viên: tối đa 10 bản, 30 ngày.
- Tài khoản phải hoạt động, không bị khóa, không có sách quá hạn chưa xử lý hoặc tiền phạt chưa thanh toán.
- Gia hạn 1 lần thêm 7 ngày nếu chưa quá hạn, không có người đặt trước; không tự gia hạn.
- Đặt trước theo đầu sách, FIFO; giữ 48 giờ.
- Phạt 1.000 đồng/bản/ngày lịch từ ngày sau hạn đến ngày trả; quá hạn từ 7 ngày thì khóa mượn mới.
- Trả ngoài giờ và bồi thường mất/hỏng có quy trình đề xuất riêng, chưa phải chính sách được quản lý thư viện duyệt.

### 2. So sánh từng thư viện

| Thư viện / nguồn | Hạn mức và kỳ hạn | Gia hạn / đặt trước | Trả trễ | Mất, hỏng, trả ngoài giờ |
|---|---|---|---|---|
| **MVP của nhóm** | SV 5 cuốn/14 ngày; GV/nhân viên 10 cuốn/30 ngày | 1 lần +7 ngày, nếu chưa trễ và không có đặt trước; FIFO, giữ 48 giờ | 1.000đ/bản/ngày lịch; khóa mượn mới khi trễ từ 7 ngày | Bồi thường cần duyệt; trả khe ngoài giờ chưa được duyệt chính thức. |
| **Thư viện ĐH Bách khoa – ĐHQG-HCM (HCMUT)** | Cán bộ/học viên/SV 5 cuốn/14 ngày; giảng viên 5 cuốn/21 ngày; chỉ một số ký hiệu sách được mang về | 1 lần +14 ngày; có thể gia hạn tại quầy hoặc online. Không gia hạn nếu quá hạn, gia hạn quá sớm, đã có đặt trước hoặc tài khoản bị khóa. Nguồn không nêu hàng chờ đặt trước. | 1.000đ/cuốn/ngày, loại trừ ngày lễ/Tết | Mất/hỏng: mua lại bản tái bản mới nhất cộng phí xử lý; nếu không mua được, 3 lần giá sách; sách không ghi giá thì giá photo 600đ/trang + đóng bìa, rồi nhân 3. Không thấy quy trình trả qua khe ngoài giờ trong nguồn đã xem. |
| **Thư viện Trường ĐH KHXH&NV – ĐHQG-HCM (USSH)** | Dịch vụ mượn về nhà công bố tài liệu tham khảo: SV/HV sau ĐH 6 cuốn/30 ngày, CB/GV 8 cuốn/30 ngày; giáo trình có kỳ hạn theo học kỳ. | Trang dịch vụ mượn liên thư viện nêu 5 cuốn/21 ngày, 2 lần gia hạn ×7 ngày; không gia hạn tài liệu quá hạn và chỉ gia hạn trước hạn 2 ngày. Đây là chính sách mượn liên thư viện, không nên đánh đồng hoàn toàn với mượn thường. | Trang dịch vụ mượn về nhà nêu 2.000đ/cuốn/ngày và khóa giao dịch 3–6 tháng nếu tái phạm từ 2 lần. | Có dịch vụ trả ngoài giờ qua form, khe trả và email xác nhận; chỉ nhận tài liệu nguyên vẹn, chưa trễ hạn, ≤1.000 trang; tài liệu ngoài điều kiện phải trả tại quầy. Mất/hỏng liên thư viện xử lý theo quy định thư viện sở hữu tài liệu. |
| **Thư viện Trường ĐH Sư phạm TP.HCM (HCMUE)** | Cán bộ/GV tối đa 5 cuốn/28 ngày; SV 2, HV cao học 3, NCS 4/28 ngày (Cẩm nang 2025–2026). | 1 lần; tối đa 14 ngày cho CB/GV và 7 ngày cho SV/HV sau ĐH. Hướng dẫn gia hạn yêu cầu trước hạn 2 ngày; không gia hạn tài liệu quá hạn. | Cẩm nang dẫn chiếu nội quy; không thấy một mức phạt quá hạn cụ thể trong nguồn này. | Mua sách mới bồi thường + 50.000đ phí xử lý; nếu không mua được thì đền 10 lần giá trị tài liệu. Nội quy có hình thức kỷ luật/khóa quyền theo số lần vi phạm. Không thấy trả khe ngoài giờ trong nguồn đã xem. |
| **Thư viện Khoa học Tổng hợp TP.HCM** | Mượn về nhà theo gói dịch vụ: 2, 3 hoặc 5 tài liệu/lần; có giới hạn tổng giá trị sách theo gói; thời gian tối đa 30 ngày. Chỉ một số nhãn/kho hoặc bản có sẵn được mượn. | FAQ hiện hành nói không có gia hạn mượn về nhà. Khi sách đang được mượn, hướng dẫn người đọc chờ/đọc bản khác; trang đã xem không mô tả hàng chờ FIFO. | FAQ nêu 2.000đ/cuốn/ngày khi giữ sách quá 30 ngày; dịch vụ mượn về còn có phí theo ngày và tiền cọc tùy giá trị sách. | Mất/hỏng phải bồi thường theo quy định thư viện; phải báo tình trạng có sẵn ngay khi nhận. Trang dịch vụ mô tả trả sách và nhận lại tiền cọc tại quầy; không thấy thùng trả ngoài giờ trong nguồn đã xem. |
| **Trung tâm TT-TV PTIT** | Nội quy công khai kèm quyết định năm 2009: SV/HV 2 cuốn/7 ngày; CB/GV 3 cuốn/15 ngày tại phòng kho mở; phòng mượn có hạn mức khác (CB/GV 7 cuốn/60 ngày; một nhóm SV tối đa 8 cuốn/150 ngày; nhóm khác 5 cuốn/150 ngày, có thể cần ký cược). | Gia hạn nếu chưa có người đăng ký mượn; nội quy không nêu rõ số lần/ngày gia hạn. | Nguồn nội quy này không ghi mức phí trễ cụ thể. | Mức xử lý do Trung tâm xem xét; yêu cầu bạn đọc kiểm tra và báo tình trạng trước khi mượn. Nội quy cũ nên chỉ dùng làm tham khảo lịch sử, cần xác minh với cơ sở TP.HCM và quy định hiện tại. |
| **Thư viện ĐH Mở TP.HCM** | Quy trình công khai được xem tập trung vào thu phạt/bồi thường, không phải bảng tổng hợp hạn mức hiện hành. | Không xác định từ tài liệu quy trình phạt. | 1.000đ/cuốn/ngày; nếu khoản phạt trên 200.000đ, bạn đọc có thể xin giảm theo quy trình duyệt. | Có kiểm tra khi trả, thông báo phương án, thu tiền/ghi giấy hẹn và lưu chứng từ. Tài liệu Việt có thể đền sách tương đương hoặc tiền theo bội số giá bìa/trang cộng phí xử lý; ngoại văn có công thức khác. Hư hỏng nhẹ và nặng có cách xử lý khác nhau. Đây là quy định riêng của trường, ban hành kèm quyết định năm 2021. |

### 3. Ưu điểm của bộ quy định nhóm

1. **Dễ vận hành và dễ hiểu:** 14 ngày cho SV, 30 ngày cho GV/nhân viên; một lần gia hạn; một mức phạt/ngày và một ngưỡng khóa 7 ngày. So với các trường có nhiều nhóm tài liệu và học kỳ, MVP đơn giản hơn.
2. **Hạn mức SV ở mức trung dung:** 5 cuốn cao hơn HCMUE/PTIT (2–4 cuốn) nhưng thấp hơn USSH (6 cuốn); phù hợp để thử tải và rủi ro tồn kho ở MVP.
3. **Cân bằng phục vụ và bảo vệ hàng chờ:** Gia hạn chỉ khi không có người đặt trước; FIFO và thời gian nhận 48 giờ giúp quy tắc phân phối sách rõ ràng hơn các nguồn không công bố hàng chờ.
4. **Mức phạt dễ dự đoán:** 1.000đ/ngày trùng với HCMUT và quy trình ĐH Mở, thấp hơn mức 2.000–5.000đ thấy ở một số dịch vụ/luồng của thư viện địa phương.
5. **Có phân biệt tài liệu lưu thông và chỉ đọc tại chỗ;** có chủ trương không tự định giá tài liệu mất/hỏng; lưu riêng lịch sử giao dịch.

### 4. Nhược điểm và thiếu sót cần chốt trước khi xem là quy định hoàn chỉnh

#### A. Mâu thuẫn điều kiện mượn và ngưỡng khóa 7 ngày — cần sửa trước khi code

Điều kiện hiện ghi “không còn sách quá hạn chưa xử lý” khiến độc giả bị chặn mượn ngay ngày đầu quá hạn. Quy tắc khác lại nói chỉ khóa khi quá hạn từ 7 ngày. Hai điều này không thể cùng có hiệu lực như nhau.

**Cần chọn một cách:** (1) chặn mượn mới ngay khi có bất kỳ sách quá hạn nào, bỏ ngưỡng 7 ngày; hoặc (2) cho mượn tiếp trong 7 ngày đầu nếu chưa vượt hạn mức/phạt và chặn từ ngày thứ 7. Đề xuất rõ ràng hơn: chặn mượn mới ngay khi có khoản mượn quá hạn; giữ mốc 7 ngày làm cảnh báo/escalation hoặc xử lý vi phạm riêng, không gọi đó là ngưỡng khóa. Nhóm cần phê duyệt lại vì đây là khác biệt nghiệp vụ.

#### B. Hạn mức của GV/nhân viên cao hơn hầu hết mẫu đối chiếu

Mức 10/30 ngày cao hơn HCMUT 5/21, HCMUE 5/28 và USSH 8/30. Điều này phục vụ đội ngũ tốt nhưng làm giảm số bản khả dụng và tăng rủi ro thất lạc/quá hạn. Cần xác định `nhân viên` có cùng quyền với giảng viên không; cán bộ thư viện/nhân viên nội bộ có thể không nên cùng nhóm với GV. Có thể đặt quota cấu hình riêng theo loại bạn đọc hoặc theo loại sách.

#### C. Mốc và cách tính tiền trễ chưa đủ chính xác

- MVP tính ngày lịch mọi ngày; HCMUT loại ngày lễ/Tết. Phải quyết định có tính ngày nghỉ, ngày thư viện đóng cửa và ngày Tết hay không.
- Phải nêu hạn 23:59 theo múi giờ Việt Nam; sự kiện mượn/trả nên lưu timestamp, không chỉ ngày.
- Chưa nêu miễn/giảm, trần tiền phạt, làm tròn, một khoản phạt đã thanh toán/được miễn có được tính lại không, hoặc xử lý tranh chấp thế nào.
- Mô hình `Loan` của nhóm là một bản vật lý trên mỗi dòng; vì vậy công thức phạt nên là tiền/ngày × số ngày cho từng `Loan`, rồi cộng các dòng. Nếu vừa lưu một dòng cho mỗi bản vừa nhân thêm số bản, hệ thống sẽ tính trùng.
- Mức 1.000đ/ngày thấp hơn một số dịch vụ địa phương (2.000–5.000đ/ngày), nhưng chỉ so sánh được khi phạm vi và điểm bắt đầu tính phạt giống nhau. Thư viện TP.HCM công bố phí mượn theo ngày/gói riêng nên không thể so trực tiếp với phí trễ.

#### D. Thiếu quy định phân biệt loại tài liệu và chu kỳ học kỳ

Nhóm có danh sách tài liệu chỉ đọc tại chỗ, nhưng cần chuyển thành trường cấu hình rõ: loại tài liệu, quyền mượn về, quyền gia hạn, số lượng, kỳ hạn, và có được đặt trước không. “Tài liệu tham khảo” không phải nơi nào cũng cấm mang về; USSH công bố nhiều tài liệu tham khảo được mượn 30 ngày. Giáo trình/học liệu theo học kỳ có thể cần hạn riêng. Không nên hard-code một cờ duy nhất trên bản sao nếu chính sách có thể áp theo bản, nhan đề, loại tài liệu hoặc nhóm bạn đọc.

#### E. Gia hạn còn thiếu một số điều kiện vận hành

Đã chốt điều kiện chưa quá hạn và không có người đặt trước, nhưng chưa xác định: được gia hạn từ ngày nào (HCMUT/HCMUE hướng dẫn trước hạn 2 ngày), hạn mới tính thêm từ hạn hiện tại hay ngày gia hạn, có gia hạn online không, có cho tiếp tục gia hạn nhiều lần ở ngoại lệ không, và có giới hạn tổng thời gian giữ sách. Phải lưu lịch sử từng lần gia hạn và người/thao tác phát sinh.

#### F. Đặt trước chưa bao phủ tình huống cạnh tranh

FIFO và 48 giờ là điểm tốt, nhưng còn thiếu: hạn 48 giờ là giờ lịch hay giờ mở cửa; nếu hết hạn ngày thư viện đóng thì dời sang ngày mở cửa tiếp theo hay không; cách báo người kế tiếp; khi người đầu hàng không đủ điều kiện mượn thì bỏ lượt hay tạm giữ; đặt trước có hiệu lực theo đầu sách hay từng ấn bản; xử lý nhiều bản trả cùng lúc; hủy đặt trước; giới hạn số đặt trước; giữ chỗ có làm giảm quota mượn không. Các thư viện tham khảo công khai thường ít mô tả queue, nên nhóm cần tự chốt quy tắc và kiểm tra.

#### G. Trả ngoài giờ còn là đề xuất, chưa thành chính sách được duyệt

USSH có form, khe trả, email xác nhận và điều kiện loại trừ hư hỏng/quá hạn/khổ lớn. Bộ nhóm đã mô tả biên nhận và các timestamp, nhưng cần quyết định: thư viện có điểm trả vật lý không; ai kiểm tra vào ca kế tiếp; bằng chứng nào xác nhận đã bỏ sách; nếu hệ thống/form/QR lỗi thì xử lý thế nào; lấy thời điểm khai báo hay nhân viên nhận để dừng phạt; sách bị ướt/mất trong khe thuộc trách nhiệm bên nào; có nhận sách quá hạn/hỏng không. Không nên ghi dịch vụ này như đang được cung cấp nếu chưa có hạ tầng và duyệt quy trình.

#### H. Quy trình mất/hỏng đã có luồng nhưng chưa có tiêu chí nhất quán

Các thư viện địa phương dùng các phương án không đồng nhất: HCMUT mua ấn bản mới hoặc bội số giá; HCMUE mua sách mới + phí xử lý 50.000đ hoặc 10 lần giá trị; ĐH Mở phân loại theo tiếng Việt/ngoại văn, số trang và mức độ hỏng; HCMUSSH dẫn chiếu quy định thư viện sở hữu. Nhóm chưa chốt:

- Bảng phân loại hư hỏng và ví dụ (hao mòn tự nhiên, bẩn/rách nhẹ, thiếu trang, ướt/mốc, mất bìa, không thể lưu thông).
- Ai có quyền phê duyệt, ngưỡng tiền nào cần cấp quản lý cao hơn, hạn ra quyết định và cách kháng nghị.
- Căn cứ giá thay thế, chấp nhận ấn bản mới hơn/tương đương, sách không còn bán, sách ngoại văn/đặc biệt, phí xử lý có chứng từ.
- Có tạm chặn mượn trong khi xác minh; khi nào dừng tính tiền trễ; xử lý khi độc giả báo mất trước hạn; xử lý nếu sách được tìm thấy sau khi đã bồi thường.
- Chứng từ thu tiền, hoàn tiền nếu cần, miễn/giảm, ghi nhận người thu và đối soát cuối ngày.

#### I. Thiếu trường hợp độc giả và quản trị tài khoản

Quy tắc chưa nêu thẻ hết hạn, mất thẻ, tài khoản liên kết nhiều vai trò, độc giả tốt nghiệp/chuyển trường, khách ngoài, thẻ liên thư viện, gia hạn tài khoản và cách xác thực hồ sơ. Thư viện thành phố hoạt động theo gói/thẻ có thời hạn và PTIT/HCMUT giới hạn dịch vụ theo đối tượng; MVP nên quy định rõ ai thuộc nhóm nào và tài khoản hoạt động tới khi nào.

#### J. Nhắc hạn và thông báo chưa có cam kết cụ thể

Mới ghi ý tưởng nhắc trước 2 ngày; chưa xác định email bắt buộc hay tùy chọn, lỗi gửi có ảnh hưởng gì, nội dung tối thiểu, lần nhắc quá hạn, cách sửa email, và bằng chứng thông báo. Nên coi thông báo là hỗ trợ; trách nhiệm trả đúng hạn vẫn theo hạn hiển thị trên phiếu/tài khoản.

### 5. Các điểm đã được bổ sung vào bộ quy định

1. Quy tắc điều kiện chặn mượn được làm rõ: bất kỳ lượt quá hạn nào cũng chặn mượn mới ngay; mốc 7 ngày chuyển trạng thái tài khoản sang `SUSPENDED`.
2. Cách tính phạt loại trừ ngày lễ/Tết và ngày thư viện đóng cả ngày; tiền phạt tính theo từng bản/lượt `Loan`, tránh nhân đôi số bản.
3. Giữ hạn mức đã chốt nhưng tách loại độc giả thành sinh viên, giảng viên, nhân viên để cấu hình độc lập.
4. Gia hạn đặt trong hai ngày cuối trước hạn, cộng vào hạn cũ; giờ nhận giữ chỗ được kéo đến ca mở cửa kế tiếp.
5. Quy trình thùng trả bổ sung biên nhận có mã, timestamp, giới hạn nhận, kiểm tra ca sau, phiếu giấy dự phòng và mốc dừng tính phạt.
6. Quy trình mất/hỏng bổ sung phân loại, căn cứ bồi thường, duyệt, khiếu nại, biên nhận và xử lý khi sách được tìm thấy.
7. Hồ sơ độc giả có ngày hiệu lực; nhắc hạn/nhắc quá hạn được ghi nhận; mô hình dữ liệu được tách chính sách lưu thông, khoản phạt và khoản thanh toán.

### 6. Việc còn cần quản lý thư viện xác nhận trước khi vận hành

1. Có điểm trả ngoài giờ thật hay không; địa điểm, lịch lấy sách, người chịu trách nhiệm và cách bảo quản trong thùng. Nếu không bố trí được, MVP chỉ nhận tại quầy.
2. Quản lý phê duyệt/công bố biểu phí sửa chữa và xử lý trước khi thu; nguồn báo giá thay thế khi sách không có giá hoặc đã ngừng bán.
3. Nhóm duyệt trần phạt đề xuất: 30.000 đồng/cuốn hoặc giá thay thế thấp hơn; xác nhận miễn/đối trừ phạt khi hồ sơ mất được chấp nhận.
4. Đồng bộ lịch nghỉ chính thức/ngày thư viện đóng cả ngày; kiểm tra cơ chế cập nhật khi có đóng cửa khẩn cấp.
5. Duyệt áp dụng thời hạn phản hồi khiếu nại 5 ngày làm việc và phân công người mở lại tài khoản sau khi trả sách, xử lý nợ, đóng hồ sơ.

### 7. Nguồn tham khảo chính thức

- [Chính sách mượn, phạt trễ và mất/hỏng — Thư viện ĐH Bách khoa, ĐHQG-HCM](https://lib.hcmut.edu.vn/tien-ich?tab=dang-ky)
- [Hướng dẫn gia hạn — Thư viện ĐH Bách khoa, ĐHQG-HCM](https://lib.hcmut.edu.vn/uploads/files/HD%20gia%20han%20tai%20lieu.pdf)
- [Dịch vụ mượn về nhà và trả ngoài giờ — Thư viện Trường ĐH KHXH&NV, ĐHQG-HCM](https://hcmussh.edu.vn/cilm/dich-vu-mien-phi)
- [Mượn liên thư viện và xử lý mất/hỏng — Thư viện Trường ĐH KHXH&NV, ĐHQG-HCM](https://hcmussh.edu.vn/cilm/muon-lien-thu-vien)
- [Cẩm nang hướng dẫn sử dụng thư viện 2025–2026 — Thư viện Trường ĐH Sư phạm TP.HCM](https://thuvien.hcmue.edu.vn/sites/default/files/Cam%20nang%20huong%20dan%20su%20dung%20thu%20vien%202025%20-%202026%20final_0.pdf)
- [Nội quy thư viện — Trường ĐH Sư phạm TP.HCM](https://thuvien.hcmue.edu.vn/node/85)
- [FAQ — Thư viện Khoa học Tổng hợp TP.HCM](https://thuvientphcm.gov.vn/nhung-cau-hoi-thuong-gap1)
- [Dịch vụ mượn tài liệu — Thư viện Khoa học Tổng hợp TP.HCM](https://www.thuvientphcm.gov.vn/Dich-vu-muon-tai-lieu)
- [Nội quy thư viện — Trung tâm TT-TV PTIT](https://lib.ptit.edu.vn/noi-quy-thu-vien/). Nội quy trên trang kèm quyết định năm 2009; cần xác minh tính hiện hành, đặc biệt với cơ sở TP.HCM.
- [Quy trình thu tiền phạt mượn quá hạn và làm hỏng, mất tài liệu — Thư viện ĐH Mở TP.HCM](https://v1.ou.edu.vn/hcqt/Quy%20trnh/TV.05.pdf), hiệu lực 01/01/2022.
