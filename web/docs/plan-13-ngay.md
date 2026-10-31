# Kế hoạch MVP 13 ngày

Mục tiêu là bản chạy thử nội bộ. Không đưa thanh toán thật hoặc dữ liệu độc giả thật vào bản đầu tiên nếu chưa hoàn tất kiểm tra và đối soát.

| Ngày | Chủ trách nhiệm | Đầu ra cần nghiệm thu |
|---|---|---|
| 1 | Cả nhóm, điều phối: bạn | Chốt quy tắc mượn/trả/phạt; mọi người chạy được dự án trên máy mình; thống nhất mô hình dữ liệu |
| 2 | Backend + người triển khai | Cấu hình môi trường, DB chia sẻ phát triển, đăng nhập và vai trò |
| 3–4 | Nhóm danh mục | Danh sách/tìm kiếm/thêm/sửa sách và độc giả; kiểm tra dữ liệu đầu vào |
| 5–7 | Nhóm lưu thông | Mượn, trả, gia hạn, đặt trước; tồn kho cập nhật nguyên tử và không thể âm |
| 8 | Nhóm cổng độc giả | Độc giả chỉ xem tài khoản, lịch sử và yêu cầu của chính mình |
| 9 | Nhóm dữ liệu | Công cụ chuyển thử dữ liệu SQLite; báo cáo bản ghi lỗi và tổng đối soát |
| 10 | Nhóm vận hành | Sao lưu/khôi phục được hướng dẫn; cấu hình máy chủ thử nghiệm và HTTPS |
| 11 | Cả nhóm | Kiểm thử các luồng chính, phân quyền và dữ liệu biên; sửa lỗi nghiêm trọng |
| 12 | Cả nhóm | Chạy thử theo kịch bản với dữ liệu tổng hợp; kiểm tra truy cập từ xa |
| 13 | Bạn nghiệm thu | Chốt bản MVP, ghi lỗi còn lại và quyết định kế hoạch triển khai tiếp |

## Chia việc

1. Bạn: chủ nghiệp vụ, chốt chính sách, kiểm tra dữ liệu cần giữ và nghiệm thu hàng ngày.
2. Người 2: nền tảng Django, đăng nhập và quyền.
3. Người 3: sách và độc giả.
4. Người 4: mượn/trả/đặt trước/tiền phạt.
5. Người 5: chuyển dữ liệu, kiểm thử, sao lưu và triển khai.

Vì cả nhóm mới làm web, ghép cặp review và đồng bộ 15 phút mỗi ngày. Không để các nhánh phát triển độc lập đến sát hạn mới tích hợp.

## Điều kiện nghiệm thu MVP

- Mỗi vai trò chỉ làm được việc được giao.
- Sách không thể được mượn vượt số bản còn; hai thao tác đồng thời không làm sai tồn kho.
- Lịch sử mượn và tiền phạt tính đúng theo quy tắc đã chốt.
- Độc giả không thể xem hồ sơ người khác.
- Bản chuyển dữ liệu có tổng đối chiếu; không ghi đè DB gốc.
- Đã diễn tập khôi phục bản sao lưu.
