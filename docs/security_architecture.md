# 🛡️ Kiến Trúc Bảo Mật (Security Architecture)
*Tài liệu thiết kế chi tiết về cơ chế bảo mật, phân quyền và lưu trữ trạng thái của AI Analytics Assistant.*

---

## 1. TỔNG QUAN LUỒNG BẢO MẬT (SECURITY PIPELINE)

Toàn bộ hệ thống bảo mật hoạt động như một "người gác cổng" nghiêm ngặt gồm 3 bước tự động hoàn toàn:

1. **Authentication (Xác thực - Bạn là ai?):** Kiểm tra JWT Token trong trình duyệt.
2. **Authorization (Định danh - Bạn làm chức vụ gì?):** Phân tích Payload của Token để biết quyền (Ví dụ: `manager_north`).
3. **RLS Context (Phân quyền dữ liệu - Bạn được xem gì?):** Tra cứu file `roles.json` để đính kèm điều kiện lọc (Ví dụ: `Region = 'Miền Bắc'`) vào câu hỏi của người dùng trước khi gửi cho AI.

-- cái này nen coi lại về phương pháp RLS --
---

## 2. QUẢN LÝ ĐĂNG NHẬP (JWT & BROWSER COOKIES)

Thay vì buộc người dùng phải đăng nhập lại mỗi khi F5 (Reload trang), hệ thống sử dụng cơ chế bảo mật tiêu chuẩn công nghiệp:

### 2.1. Mã thông hành (JWT Token)
- Khi User đăng nhập thành công, FastAPI cấp một chuỗi JWT được mã hóa bằng thuật toán `HS256` với khóa bí mật `JWT_SECRET_KEY` (lưu trong file `.env`).
- **Thời hạn:** Mặc định được cấu hình là **8 tiếng** (đúng 1 ngày làm việc). Sau 8 tiếng, thư viện `PyJWT` sẽ tự động từ chối token và yêu cầu đăng nhập lại.
- **Tính chất Stateless:** FastAPI **không** lưu danh sách Token. Việc xác thực hoàn toàn dựa trên toán học (giải mã bằng Secret Key), giúp server cực nhẹ.

### 2.2. Chiếc túi Cookie của trình duyệt
- Thay vì lưu trên RAM dễ mất, Token được lưu vào **Cookies** của trình duyệt Chrome/Edge (sử dụng `streamlit-cookies-manager`).
- Cookie được cấu hình `HttpOnly = True` để ngăn chặn hacker dùng mã độc JavaScript đánh cắp (Tấn công XSS).
- **Cơ chế F5 (Reload):** Khi trang bị F5, RAM bị xóa nhưng trình duyệt tự động móc Token từ Cookie ra gửi lại cho Server. Hệ thống âm thầm đăng nhập lại mà người dùng không hề hay biết!

---

## 3. QUẢN LÝ LỊCH SỬ CHAT (SESSIONS.DB)

### 3.1. Phân lập dữ liệu nghiêm ngặt
- Hệ thống sử dụng SQLite (`data/sessions.db`) lưu trên ổ cứng Server Render.
- Mỗi lượt hội thoại được dán nhãn bằng `user_id`. Do đó, khi User A (Trưởng phòng Bắc) bấm F5, server chạy lệnh `SELECT * FROM sessions WHERE user_id = 'User A'`, đảm bảo User A **tuyệt đối không bao giờ nhìn thấy** lịch sử chat của User B.

### 3.2. Lưu trữ Biểu đồ thông minh (Không lưu file ảnh)
- Để phục hồi biểu đồ sau khi F5 mà không làm nặng Database, hệ thống KHÔNG lưu hình ảnh (`.png`).
- Hệ thống chỉ lưu một chuỗi **Mã JSON cấu hình của Plotly** vào chung với tin nhắn. Khi F5, trình duyệt đọc mã JSON đó và vẽ lại biểu đồ tương tác ngay lập tức trong 0.1 giây mà không cần chạy lại truy vấn SQL.

---

## 4. CƠ CHẾ PHÂN QUYỀN MỨC DÒNG (ROW LEVEL SECURITY - RLS)

Đây là "trái tim" bảo vệ dữ liệu doanh nghiệp, đảm bảo mỗi người chỉ xem được những gì họ được phép.

### 4.1. Không sử dụng Code SQL Injection
Thay vì dùng thư viện `sqlglot` để tự đục lỗ và chèn mã `WHERE` bằng Python (Rất khó bảo trì, dễ lỗi cú pháp khi JOIN nhiều bảng), hệ thống chọn cách thông minh hơn: **Prompt Engineering**.

### 4.2. Luồng hoạt động (Ví dụ thực tế)
- **Luật:** File `roles.json` khai báo `manager_north` bắt buộc phải có điều kiện `Region = 'Miền Bắc'`.
- **User hỏi:** *"Tổng doanh thu các sản phẩm bao nhiêu?"* (Cố tình hỏi thiếu để xem lén cả nước).
- **Security Engine can thiệp:** Tự động nhào nặn Prompt và "ra lệnh" cho con AI Groq Llama: 
  > *"Này AI, User này là Trưởng phòng Miền Bắc. Trong mọi câu SQL bạn viết ra, BẮT BUỘC phải chèn đoạn `WHERE Region = 'Miền Bắc'` vào."*
- **Kết quả:** Con AI Llama "tự giác" tuân thủ, viết ra câu SQL đã được chèn sẵn quyền. Database chỉ việc chạy và trả về đúng dữ liệu Miền Bắc. An toàn, nhàn nhã và không bao giờ lỗi cú pháp!

---

## 5. RÀNH GIỚI AN TOÀN DỮ LIỆU (DATA PRIVACY BOUNDARY)

Hệ thống cam kết mức độ an toàn dữ liệu chuẩn Enterprise:

1. **Với Trình duyệt (Cookie):** Chỉ lưu JWT Token. **TUYỆT ĐỐI KHÔNG** lưu dữ liệu doanh nghiệp hay doanh thu xuống máy tính của User.
2. **Với AI API bên ngoài (Gemini / Cohere / Groq):** 
   - Chỉ truyền Tên Cột, Tên Bảng (Metadata) và Câu hỏi.
   - **TUYỆT ĐỐI KHÔNG** gửi dữ liệu thô (hàng triệu dòng chứa tên khách hàng, số tiền thực tế) lên các máy chủ AI.
3. **Nơi thực thi (Fabric/SQLite):** Việc tính toán `SUM`, `AVG` trên dữ liệu thô diễn ra **100% cục bộ** bên trong hạ tầng Database nội bộ của doanh nghiệp.
4. **Cơ chế Template Injection (Zero Data Sharing):** Ở bước cuối cùng, để viết nhận xét, hệ thống KHÔNG gửi con số tổng hợp (Ví dụ: `10 tỷ`) cho Gemini. Thay vào đó, Gemini được yêu cầu sinh ra một "Văn mẫu" với các khoảng trống (Ví dụ: *"Doanh thu là {revenue}..."*). Sau đó, máy chủ Python nội bộ tự động lấp con số thực tế vào khoảng trống đó. Bằng cách này, AI hoàn toàn bị "bịt mắt" trước mọi con số kinh doanh nhạy cảm của công ty!
