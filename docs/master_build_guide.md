# 🛠️ MASTER BUILD GUIDE: HƯỚNG DẪN THỰC THI CODE TỪ A-Z
*Tài liệu này là "Bản giao việc" (Task List) chi tiết ở cấp độ Lập trình viên, ánh xạ 12 bước lý thuyết vào đúng cấu trúc thư mục của dự án.*

---

## 🎯 GIAI ĐOẠN 1: SETUP NỀN TẢNG (FOUNDATION)
*Làm móng cho dự án, cài đặt môi trường và kết nối cơ bản.*

- [ ] **Bước 1.1: Môi trường & Dependencies**
  - File: `requirements.txt`
  - Cập nhật thư viện: fastapi, streamlit, sqlalchemy, cohere, groq, chromadb...
- [ ] **Bước 1.2: Cấu hình hệ thống (Config)**
  - File: `.env` và `core/config.py`
  - Khai báo API Keys và Database URL. Viết class `Settings` bằng Pydantic.
- [ ] **Bước 1.3: Dựng Database nội bộ (Mock DB)**
  - File: `data/mock_db_setup.py`
  - Tạo file SQLite chứa 3 bảng mẫu: Orders, Customers, Products để test.
- [ ] **Bước 1.4: Khởi tạo Backend & Frontend rỗng**
  - File: `main.py` (FastAPI) và `ui.py` (Streamlit)
  - Đảm bảo Backend gọi được `http://localhost:8000/api/health` và Frontend hiển thị giao diện.

---

## 🛡️ GIAI ĐOẠN 2: BẢO MẬT & KẾT NỐI DỮ LIỆU (DATA LAYER)
*Xây dựng cửa ngõ bảo vệ hệ thống trước khi ráp AI vào.*

- [ ] **Bước 2.1: Module Security (JWT & RLS)**
  - File: `modules/security/auth.py`
  - Code cơ chế cấp phát JWT Token. Viết hàm sinh luật RLS (VD: Ép Region='Miền Bắc').
- [ ] **Bước 2.2: Module Data Source (Truy xuất DB)**
  - File: `modules/data_source/fabric.py` và `modules/data_source/sqlite.py`
  - Code class `DataConnector` để chọc vào Database.
  - **⚠️ Chốt chặn quan trọng:** Cài đặt hàm `Query Limiter` (luôn ép `LIMIT 100` nếu câu lệnh là SELECT *).
- [ ] **Bước 2.3: Data Profiler (Quét mẫu dữ liệu)**
  - File: `modules/data_source/profiler.py`
  - Viết code quét các cột Low Cardinality (< 50 giá trị). Lưu vào cache/json.

---

## 🧠 GIAI ĐOẠN 3: XÂY DỰNG BỘ NÃO AI (AI CORE)
*Lắp ráp hệ thống RAG và LLM (Chặng xương xẩu nhất).*

- [ ] **Bước 3.1: Conversation Manager (Quản lý ngữ cảnh)**
  - File: `modules/conversation/memory.py`
  - Code logic lưu/lấy 5 câu chat gần nhất từ `sessions.db` (SQLite).
- [ ] **Bước 3.2: NLU Engine (Phân tích Ý định)**
  - File: `modules/nlu/router.py`
  - Dùng Groq/Llama nhận diện câu hỏi rác vs. câu hỏi Data. Viết lại câu hỏi (Query Rewriting).
- [ ] **Bước 3.3: Schema RAG (ChromaDB + Cohere)**
  - File: `modules/schema/vector_db.py` và `modules/schema/retriever.py`
  - Code hàm nhúng cấu trúc Bảng vào ChromaDB. 
  - Tích hợp **Từ điển Tiếng lóng** (`synonyms.json`) và màng lọc **Tỉa Cột** (Loại bỏ cột rác).
  - Tích hợp **Adaptive Reranker** (Lọc Top 10 xuống Top 3).
- [ ] **Bước 3.4: Text-to-SQL Engine (Trái tim hệ thống)**
  - File: `modules/sql/generator.py`
  - Code Prompt gửi Llama 3.3. **Bắt buộc cài luật `ILIKE`** cho cột kiểu TEXT.
- [ ] **Bước 3.5: SQL Validator (Kiểm duyệt lỗi)**
  - File: `modules/sql/validator.py`
  - Nếu SQL chạy lỗi, bốc mã lỗi thảy lại cho Llama sửa (vòng lặp tối đa 3 lần).

---

## 📊 GIAI ĐOẠN 4: PHÂN TÍCH & TRÌNH BÀY (OUTPUT & VISUALIZATION)
*Xử lý cục dữ liệu thô thành Báo cáo đẹp mắt.*

- [ ] **Bước 4.1: Data Analysis (Nhận xét tự động bằng Gemini)**
  - File: `modules/analysis/insight.py`
  - Dùng **Template Injection**: Che toàn bộ số liệu thật, chỉ truyền Template cho Gemini sinh văn mẫu, sau đó Python lấp số thật vào. (Bảo mật 100%).
- [ ] **Bước 4.2: Data Visualization (Vẽ biểu đồ Plotly)**
  - File: `modules/visualization/charts.py`
  - Viết code Python chuyển DataFrame thành JSON cấu hình Plotly. Không lưu file ảnh.

---

## 🚀 GIAI ĐOẠN 5: LẮP RÁP PIPELINE & API
*Ghép 10 mảnh vỡ ở trên thành một dây chuyền tự động hóa hoàn chỉnh.*

- [ ] **Bước 5.1: Pipeline Orchestrator**
  - File: `core/orchestrator.py`
  - Nối luồng dữ liệu chạy xuyên suốt từ Bước 3.1 -> Bước 4.2.
- [ ] **Bước 5.2: API Endpoints**
  - File: `main.py`
  - Bọc Pipeline ở trên vào API `/api/query` (Sử dụng SSE Streaming để chữ hiện ra từ từ).
- [ ] **Bước 5.3: Giao diện hoàn chỉnh (Streamlit UI)**
  - File: `ui.py`
  - Gắn API vào UI. Hiển thị Chat, Biểu đồ động, Lịch sử chat và Nút Tải báo cáo.
- [ ] **Bước 5.4: Local Cache Engine**
  - File: `modules/data_source/cache.py`
  - Làm lớp khiên bảo vệ ngoài cùng: Băm câu hỏi tìm Cache trước khi gọi API.

---

**✨ TỔNG KẾT:** Nếu chúng ta đi đúng theo thứ tự 5 Giai đoạn (21 Bước code) này, dự án sẽ không bao giờ bị rối và hoàn toàn tương thích với kiến trúc "Zero-Cost + Siêu bảo mật" mà chúng ta đã thiết kế!
