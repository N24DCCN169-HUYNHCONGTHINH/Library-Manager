# Kế hoạch dài hạn — Library Manager

Cập nhật ngày 07/11/2026.

## Mục tiêu và phạm vi

Phát triển bản web Django thành sản phẩm có thể vận hành bằng dữ liệu thật, triển khai cho nhiều chi nhánh và bàn giao cho doanh nghiệp. Giả định triển khai đầu tiên tại một điểm phục vụ của một tổ chức. Nếu đơn vị đầu tiên cần chuyển từ một hệ thống thư viện khác, đưa biên mục MARC21 và nhập dữ liệu lên giai đoạn P0.

Bản web đã có danh mục, quản lý từng bản sách theo mã vạch, mượn/trả, gia hạn, đặt trước, cổng độc giả, phân quyền và MFA cho nhân viên. Các đầu việc dưới đây gồm cả phần cần xây thêm và phần cần nghiệm thu trên môi trường thực tế.

## P0 — Sẵn sàng thí điểm với dữ liệu thật

- [ ] **01. Phạm vi và chính sách.** Chọn đơn vị thí điểm, người phụ trách và người nghiệm thu. Chốt nhóm độc giả, loại tài liệu, hạn mức, lịch nghỉ, phí, ngoại lệ và thẩm quyền. Lưu phiên bản chính sách để giải thích giao dịch cũ.
- [ ] **02. Kiểm kê theo mã vạch.** Mở đợt theo kho hoặc kệ, quét mã, phát hiện bản sai vị trí, mã trùng và bản không tìm thấy. Phân biệt thất lạc với mất đã xác nhận. Duyệt chênh lệch, lưu người xử lý và cập nhật khả năng cho mượn.
- [ ] **03. Mất, hỏng và bồi thường.** Theo dõi từ khai báo đến đóng hồ sơ, gồm bằng chứng, định giá, khiếu nại và phê duyệt. Xử lý tìm lại trước hoặc sau quyết toán, miễn giảm, bồi thường bằng hiện vật và mở lại quyền mượn.
- [ ] **04. Khoản thu và đối soát.** Chuẩn hóa biên nhận, thu một phần, nộp thừa, hoàn tiền, ghi có và đối trừ. Liên kết điều chỉnh với chứng từ gốc, phân quyền duyệt và đối soát cuối ca. Chống ghi nhận trùng khi thao tác lặp hoặc mất kết nối.
- [ ] **05. Tính nhất quán tại quầy.** Thử cấp cùng một bản từ hai quầy, trả trùng, gia hạn khi có đặt trước, hết hạn giữ chỗ và máy quét gửi lặp. Quy định cách phục vụ khi mất mạng và nhập bù có đối soát.
- [ ] **06. Chuyển dữ liệu Windows.** Ánh xạ đầu sách, bản vật lý, độc giả, lượt mượn đang mở và số dư. Chạy thử trên bản sao, tách bản ghi thiếu căn cứ, đối soát số liệu. Chốt thời điểm ngừng ghi trên bản Windows và phương án quay lại.
- [ ] **07. Tác vụ tự động.** Lập lịch hết hạn giữ chỗ, cập nhật quá hạn, hết hạn thẻ và nhắc trả. Theo dõi lần chạy, lỗi và trạng thái gửi. Thử lại có kiểm soát, kiểm tra múi giờ, ngày nghỉ và gia hạn sát lúc gửi nhắc.
- [ ] **08. Bảo mật và quyền riêng tư.** Kiểm thử quyền theo vai trò, cơ sở và hồ sơ qua giao diện, API và tệp xuất. Hoàn thiện thu hồi quyền, nhật ký thao tác quan trọng, quản lý bí mật, mã hóa và chính sách lưu/xóa dữ liệu. Đối chiếu nghĩa vụ dữ liệu với đơn vị thí điểm và dùng OWASP ASVS để rà soát kỹ thuật.
- [ ] **09. Triển khai và khôi phục.** Tách môi trường phát triển, nghiệm thu và sản xuất. Tự động hóa kiểm thử và phát hành, chuẩn bị quay lui. Sao lưu cơ sở dữ liệu và tệp ngoài máy chủ chính. Diễn tập khôi phục, đo thời gian phục hồi và mức mất dữ liệu, đặt cảnh báo cho ứng dụng, cơ sở dữ liệu và tác vụ nền.
- [ ] **10. Nghiệm thu tại quầy.** Cho thủ thư, quản lý và độc giả thử trên thiết bị thật. Kiểm thử PostgreSQL, tải, phân quyền, thao tác đồng thời và phục hồi. Chốt ngưỡng phản hồi, tài liệu theo vai trò và người tiếp nhận sự cố.

**Điều kiện mở thí điểm.** Dữ liệu đã đối soát, khôi phục được từ bản sao lưu, ngoại lệ tại quầy đã được thử và người phụ trách thư viện ký nghiệm thu.

## P1 — Hoàn thiện nghiệp vụ thư viện chuyên nghiệp

- [ ] **11. Biên mục và trao đổi dữ liệu.** Chuẩn hóa đầu sách, ấn bản, thông tin lưu giữ và bản vật lý. Kiểm soát tác giả, chủ đề, phân loại và mã xếp giá. Nhập/xuất MARC21, xem trước ánh xạ, phát hiện trùng, hợp nhất có lưu vết và kiểm tra xuất rồi nhập lại. Kết nối nguồn tra cứu biểu ghi phù hợp.
- [ ] **12. Bổ sung tài liệu và vòng đời tài sản.** Quản lý đề xuất, duyệt mua, nhà cung cấp, ngân sách, đơn mua, nhận từng phần và hóa đơn. Ghi nguồn tiếp nhận, tài liệu tặng, sửa chữa và thanh lý.
- [ ] **13. Ấn phẩm định kỳ và tài nguyên số.** Theo dõi đăng ký, kỳ dự kiến, kỳ thiếu và gia hạn. Quản lý gói thuê bao, giấy phép, hạn truy cập và phạm vi người dùng theo nhu cầu của khách hàng.
- [ ] **14. Nhiều chi nhánh.** Phân biệt cơ sở sở hữu, vị trí hiện tại và điểm nhận. Hỗ trợ chuyển kho, đang vận chuyển, nhận bàn giao, trả khác chi nhánh và đặt trước liên chi nhánh. Kiểm tra quyền, lịch và chính sách từng điểm.
- [ ] **15. Tra cứu và khả năng tiếp cận.** Tìm tiếng Việt có/không dấu, ISBN và mã vạch. Lọc theo ấn bản, cơ sở, tình trạng. Tối ưu bàn phím, máy quét, in nhãn và biên nhận. Kiểm tra di động, trình đọc màn hình và độ tương phản theo mục tiêu WCAG 2.2 AA.
- [ ] **16. Báo cáo và quản trị.** Thống nhất cách tính lượt mượn, quá hạn, sử dụng kho, chênh lệch kiểm kê và công nợ. Lọc theo kỳ và cơ sở, truy ngược giao dịch theo quyền và giới hạn dữ liệu cá nhân trong bản xuất.

## P2 — Sẵn sàng triển khai và hỗ trợ doanh nghiệp

- [ ] **17. Mô hình triển khai và cách ly khách hàng.** Chọn triển khai riêng hoặc dịch vụ dùng chung. Nếu dùng chung, cách ly truy vấn, tệp, tìm kiếm, bộ nhớ đệm, tác vụ nền, nhật ký và sao lưu. Thử truy cập chéo và quy trình xuất, bàn giao, xóa dữ liệu từng khách hàng.
- [ ] **18. Danh tính doanh nghiệp.** Tích hợp SSO theo nhà cung cấp cụ thể. Đồng bộ người dùng khi cần, ánh xạ nhóm quyền, xử lý chuyển bộ phận và thu hồi quyền khi nghỉ việc. Kiểm soát và ghi vết truy cập hỗ trợ.
- [ ] **19. API, thiết bị và tích hợp.** Cung cấp API có phiên bản, tài liệu, giới hạn truy cập và nhật ký. Chọn tích hợp nhân sự, kế toán, thanh toán, máy tự mượn, RFID, danh mục liên hợp hoặc mượn liên thư viện theo nhu cầu. Kiểm thử gián đoạn và gửi lại giao dịch.
- [ ] **20. Hiệu năng và nâng cấp.** Đo tải theo quy mô dữ liệu và số quầy. Tối ưu truy vấn và tác vụ nặng, diễn tập nâng cấp trên bản sao, kiểm tra tương thích và quay lui. Duy trì một dòng phiên bản có cấu hình theo khách hàng.
- [ ] **21. Bàn giao và hỗ trợ.** Chuẩn hóa cài đặt, đào tạo, nhập/xuất và xử lý sự cố. Chốt cam kết dịch vụ dựa trên số liệu đo được. Chuẩn bị hồ sơ bảo mật, quy trình báo lỗ hổng, điều khoản dữ liệu, giấy phép và quy trình kết thúc hợp đồng.

## Thứ tự khởi động

1. Chọn đơn vị thí điểm và thống nhất các kịch bản nghiệm thu.
2. Bắt đầu kiểm kê mã vạch, sau đó hoàn thiện mất/hỏng và điều chỉnh khoản thu. Song song, đối soát chuyển dữ liệu, lập lịch tác vụ và diễn tập khôi phục.
3. Chạy trọn chu kỳ từ nhập bản sách đến báo cáo cuối kỳ. Ghi nhận lỗi tại quầy và đóng các lỗi ảnh hưởng đến dữ liệu hoặc giao dịch trước khi mở rộng.
4. Xếp lại P1 và P2 theo yêu cầu của khách hàng kế tiếp. Khi đưa mỗi đầu việc vào thực hiện, bổ sung người phụ trách, phụ thuộc, tiêu chí hoàn thành và bằng chứng nghiệm thu.

## Tài liệu tham chiếu

- [Tài liệu bản web](../README.md)
- [Các hạng mục vận hành còn mở](hoan-thien-van-hanh.md)
- [Kế hoạch MVP 13 ngày](plan-13-ngay.md)
- [Library of Congress — MARC21](https://www.loc.gov/marc/marcdocz.html)
- [Koha — Bổ sung tài liệu](https://koha-community.org/manual/latest/en/html/acquisitions.html)
- [FOLIO — Bổ sung tài liệu](https://docs.folio.org/docs/acquisitions/)
- [OWASP ASVS](https://asvs.owasp.org/)
- [WCAG 2.2](https://www.w3.org/TR/WCAG22/)
