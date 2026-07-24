# 🗺️ Lộ Trình Triển Khai Dự Án (Project Execution Phases)
*Tài liệu tổng hợp các "Chặng" (Phases) thực thi để xây dựng AI Analytics Assistant từ con số 0 đến khi lên Production.*

---

## 🏁 CHẶNG 1: THIẾT KẾ KIẾN TRÚC & LÝ THUYẾT (DESIGN PHASE)
*(Trạng thái: ✅ Đã hoàn thành 100%)*
- **Mục tiêu:** Chốt chặn mọi lỗ hổng logic, bảo mật và kỹ thuật trước khi gõ dòng code đầu tiên.
- **Thành quả đạt được:**
  - `roadmap_v3_zero_cost.md`: Luồng 12 bước Text-to-SQL tối ưu.
  - `security_architecture.md`: Cơ chế bảo mật JWT, Cookie, RLS và Zero Data Sharing.
  - `local_cache_architecture.md`: Cơ chế bộ nhớ đệm chống tắc nghẽn.
  - `conversation_manager_architecture.md`: Quản lý bộ nhớ ngữ cảnh (Memory).
  - `rag_engine_architecture.md`: 7 Kỹ thuật RAG Enterprise và Query Limiter.

---

## 🛠️ CHẶNG 2: XÂY DỰNG NỀN TẢNG (FOUNDATION SETUP)
*(Trạng thái: ⏳ Chuẩn bị thực hiện)*
- **Mục tiêu:** Dựng bộ khung xương cho dự án.
- **Công việc chi tiết:**
  - Cài đặt môi trường ảo (Python Virtual Environment) & các thư viện cần thiết.
  - Cấu hình file `.env` (API Keys: Groq, Gemini, Cohere).
  - Dựng khung **FastAPI** (Backend) chuẩn RESTful.
  - Dựng giao diện cơ bản bằng **Streamlit** (Frontend).
  - Khởi tạo Database nội bộ (`sqlite3`) làm môi trường giả lập thay cho Microsoft Fabric.

---

## 🧠 CHẶNG 3: XÂY DỰNG BỘ NÃO AI (CORE AI ENGINES)
*(Trạng thái: ⏳ Chờ)*
- **Mục tiêu:** Lắp ráp hệ thống NLU, RAG và Text-to-SQL. Đây là chặng khó nhất.
- **Công việc chi tiết:**
  - Tích hợp **Cohere v3** và **ChromaDB** để làm kho chứa Schema (RAG).
  - Viết code Python cho màng lọc **Tỉa Cột (Column Pruning)** và **Từ điển Tiếng lóng**.
  - Tích hợp **Groq (Llama 3.3)** để sinh mã SQL (Áp dụng luật `ILIKE` cho cột Text).
  - Viết module **Security Engine** tiêm luật RLS vào Prompt.
  - Tích hợp **Gemini Flash** làm nhiệm vụ sinh Văn mẫu (Template Injection) để nhận xét số liệu.

---

## 🔗 CHẶNG 4: LẮP RÁP LUỒNG DỮ LIỆU & KIỂM THỬ (INTEGRATION & TESTING)
*(Trạng thái: ⏳ Chờ)*
- **Mục tiêu:** Nối Backend, AI và Frontend lại với nhau cho chảy mượt mà qua 12 bước.
- **Công việc chi tiết:**
  - Viết module kết nối Database (DataConnector) kèm "Phanh tay điện tử" `LIMIT 100` (Query Limiter).
  - Viết code vẽ biểu đồ tương tác bằng **Plotly** hiển thị lên Streamlit.
  - Tích hợp tính năng Chat Streaming (Chữ hiện ra từ từ) mang lại trải nghiệm như ChatGPT.
  - Giả lập 10 tình huống khó của người dùng để kiểm thử hệ thống.

---

## 🚀 CHẶNG 5: TRIỂN KHAI THỰC TẾ (PRODUCTION DEPLOYMENT)
*(Trạng thái: ⏳ Chờ)*
- **Mục tiêu:** Đưa ứng dụng ra khỏi máy tính cá nhân để phục vụ toàn công ty.
- **Công việc chi tiết:**
  - Đóng gói toàn bộ ứng dụng bằng **Docker**.
  - Triển khai Backend và Frontend lên máy chủ đám mây (Cloud Server) như Render / AWS.
  - Cài đặt **Cron-job** chạy ngầm ban đêm để tự động kiểm thử các câu SQL mẫu (Auto-Tested Few-shot).
  - Bàn giao sản phẩm hoàn thiện.
