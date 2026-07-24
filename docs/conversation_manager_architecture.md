# 🧠 Kiến Trúc Quản Lý Hội Thoại (Conversation Manager)
*Tài liệu thiết kế chi tiết về cơ chế lưu trữ bộ nhớ, lịch sử chat và phục hồi giao diện của AI Analytics Assistant.*

---

## 1. TỔNG QUAN (OVERVIEW)

**Conversation Manager** đóng vai trò là "Vùng Hải Mã" (bộ nhớ) của hệ thống. Trong các ứng dụng Web thông thường (đặc biệt là Streamlit), bộ nhớ RAM sẽ bị xóa sạch mỗi khi người dùng tải lại trang (F5). 

Nhiệm vụ của Conversation Manager là:
1. **Lưu trữ vĩnh viễn:** Đảm bảo lịch sử chat không bị mất khi F5 hoặc khi Server khởi động lại.
2. **Cung cấp ngữ cảnh (Context):** Cung cấp các câu hỏi cũ để AI (Gemini) có thể hiểu được các câu hỏi nối tiếp (Ví dụ: *"Còn miền Nam thì sao?"*).
3. **Phân lập người dùng:** Đảm bảo ai đăng nhập vào thì chỉ thấy lịch sử chat của người đó.

---

## 2. KIẾN TRÚC LƯU TRỮ (STORAGE ARCHITECTURE)

Hệ thống sử dụng **SQLite** (`data/sessions.db`) làm cơ sở dữ liệu chính cho Conversation Manager thay vì dùng RAM (`st.session_state`) hay các hệ cơ sở dữ liệu cồng kềnh.

**Tại sao lại là SQLite?**
- **$0 Chi phí:** Không cần thuê máy chủ Database riêng.
- **Tốc độ siêu tốc (<1ms):** Đọc/Ghi trực tiếp trên ổ cứng máy chủ cực kỳ nhanh.
- **Bảo toàn dữ liệu (Persistence):** Khi deploy lên Render, file `sessions.db` được đặt trong Docker Volume. Dù Server có cúp điện hay khởi động lại, lịch sử chat vẫn còn nguyên vẹn.

---

## 3. CẤU TRÚC DỮ LIỆU (SCHEMA DESIGN)

Bảng `sessions` trong cơ sở dữ liệu được thiết kế vô cùng tinh gọn:

| Cột (Column) | Kiểu dữ liệu | Ý nghĩa |
| :--- | :--- | :--- |
| `session_id` | TEXT (PK) | Mã phiên chat duy nhất (Ví dụ: `sess_12345`) |
| `user_id` | TEXT | Mã người dùng sở hữu phiên chat này |
| `memory_json` | TEXT | **TRÁI TIM CỦA HỆ THỐNG:** Lưu toàn bộ chuỗi Chat dưới dạng JSON |
| `last_query` | TEXT | Câu hỏi gần nhất của User |
| `created_at` | TIMESTAMP | Thời gian tạo phiên chat |

### 🔍 Bí mật của cột `memory_json`
Thay vì tạo ra hàng ngàn dòng trong database cho mỗi câu chat, hệ thống lưu toàn bộ 1 cuộc hội thoại vào chung **1 ô duy nhất** dưới dạng mảng JSON. 

Ví dụ nội dung thực tế lưu trong `memory_json`:
```json
[
  {
    "role": "user", 
    "content": "Vẽ biểu đồ doanh thu Miền Bắc."
  },
  {
    "role": "ai", 
    "content": "Đây là biểu đồ của bạn:",
    "chart_json": "{\"data\": [{\"x\": [\"T1\", \"T2\"], \"y\": [100, 200], \"type\": \"bar\"}]}"
  }
]
```
👉 **Điểm đột phá:** Cột này không chỉ lưu "Chữ", mà lưu luôn cả **Mã nguồn vẽ biểu đồ (chart_json) của Plotly**. Tránh tuyệt đối việc phải lưu file ảnh (`.png`) gây phình to database!

---

## 4. CƠ CHẾ HOẠT ĐỘNG THỰC TẾ (WORKFLOW)

### Trường hợp 1: Khi User đang chat liên tục
1. User gõ: *"Còn miền Nam thì sao?"*
2. **Conversation Manager:** Đọc file `sessions.db`, bốc ra 3-5 câu chat gần nhất.
3. Gửi chuỗi lịch sử đó cho **Gemini Flash (NLU Engine)**.
4. Gemini Flash dựa vào lịch sử để thực hiện **Query Rewriting**, dịch câu hỏi thành: *"Vẽ biểu đồ doanh thu Miền Nam."*
5. AI sinh SQL, truy vấn Database, vẽ biểu đồ.
6. **Conversation Manager:** Ghi nối (Append) câu hỏi mới và biểu đồ mới vào lại cột `memory_json`.

### Trường hợp 2: Khi User bấm F5 (Reload trang)
1. User bấm F5, màn hình Streamlit trắng tinh, RAM bị xóa sạch.
2. Trình duyệt tự động lấy JWT Token từ Cookie gửi xuống Server.
3. Server giải mã Token, lấy ra `user_id`.
4. **Conversation Manager:** Lập tức chạy lệnh `SELECT memory_json FROM sessions WHERE user_id = ...`
5. Code Python đọc chuỗi JSON, nhả "Chữ" vào bong bóng chat, nhả "Mã Plotly" ra thư viện vẽ biểu đồ.
6. **Kết quả:** Màn hình khôi phục 100% y như cũ trong vỏn vẹn **0.1 giây**, biểu đồ vẫn có thể tương tác (rê chuột) mà không cần phải tốn tiền gọi lại LLM hay chạy lại lệnh SQL nào cả!

---

## 5. TỔNG KẾT
Sự kết hợp giữa **SQLite** và cột lưu trữ **Mã JSON cấu trúc tĩnh (Text + Plotly config)** giúp Conversation Manager của hệ thống đạt được 3 tiêu chí: **Zero-cost, Siêu nhẹ, và Bất tử trước mọi thao tác F5 của người dùng.**
