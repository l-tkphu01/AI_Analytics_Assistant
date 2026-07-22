# Các Quy tắc Toàn cục cho Trợ lý AI Analytics (AI Analytics Assistant)

## Hướng dẫn sinh lệnh SQL (Text-to-SQL Guidelines)
- **Xử lý Cột có độ phân tán cao (High Cardinality Columns):** Tuyệt đối KHÔNG dùng lệnh `SELECT DISTINCT` để nhồi nhét tất cả các giá trị độc nhất vào Prompt đối với những cột chứa nhiều giá trị (như `Tên Khách Hàng`, `Tên Sản Phẩm`... có hơn 50 giá trị), vì việc này sẽ làm nổ (tràn) bộ nhớ ngữ cảnh (Context Window) của AI.
- **Chiến lược phòng thủ ILIKE (ILIKE Fallback Strategy):** Đối với các cột dữ liệu Dạng Chữ (Text) có nhiều giá trị, LUÔN LUÔN chỉ thị rõ ràng cho LLM (trong System Prompt) KHÔNG ĐƯỢC dùng toán tử dấu bằng `=`. LLM BẮT BUỘC phải dùng `ILIKE '%...%'` hoặc `LOWER(column) LIKE '%...%'` khi muốn lọc dữ liệu chữ. Việc này nhằm xử lý triệt để các lỗi về dấu tiếng Việt, khoảng trắng và chữ hoa chữ thường (Ví dụ: `WHERE LOWER(CustomerName) LIKE LOWER('%Nguyễn Văn A%')`). Đây là chiến lược "Zero-Cost" chính thức của dự án để giải quyết bài toán Nhận diện Thực thể.

## Hướng dẫn Trình bày Dữ liệu (Step 11 - Data Visualization)
- **Chống vẽ biểu đồ vô nghĩa (Dynamic Chart Fallback):** AI phải phân tích kỹ lưỡng cấu trúc của bảng dữ liệu SQL vừa truy xuất được. Nếu dữ liệu chỉ đơn thuần là một danh sách liệt kê chi tiết (Ví dụ: Danh sách 5 hóa đơn cụ thể gồm Tên khách và Giá tiền) mà không hề có trục thời gian (Time-series) hay các hàm gom nhóm tính toán (SUM, COUNT, GROUP BY), thì AI BẮT BUỘC phải trả về kết quả `chart_type = None`. Giao diện hệ thống sẽ mặc định hiển thị Bảng Dữ liệu (DataFrame) thay vì cố gắng ép vẽ ra một cái biểu đồ vô nghĩa.

## Hướng dẫn Bảo mật NLU (NLU Security Guardrails)
- **Chống Prompt Injection (Câu hỏi nửa chính nửa tà):** Khi code System Prompt cho module NLU, BẮT BUỘC phải rào luật đánh giá TOÀN BỘ Ý ĐỒ (Intent). Nếu phát hiện bất kỳ dấu hiệu tà đạo nào ở vế sau (như "để gửi spam", "hack", "xóa dữ liệu"), mặc dù vế trước hợp lệ ("Lấy danh sách khách hàng"), AI phải ngay lập tức lật cờ `is_safe = False` và chặn đứng truy vấn. Tuyệt đối không được thỏa hiệp với các câu hỏi có mục đích phá hoại.
