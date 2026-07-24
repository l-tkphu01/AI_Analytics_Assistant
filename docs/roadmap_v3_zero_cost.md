# 🚀 Roadmap Hoàn Chỉnh AI Analytics Assistant (Phiên Bản 3.2 - Tối Ưu Zero Cost)

## 1. TỔNG QUAN HỆ THỐNG
Dự án là một trợ lý ảo Data Analytics (Text-to-SQL) hoạt động dựa trên chiến lược **"Zero-Cost"**. Hệ thống sử dụng 100% các API miễn phí nhưng được thiết kế với kiến trúc chuẩn Enterprise, đảm bảo độ chính xác cao, bảo mật dữ liệu và linh hoạt khi đổi nguồn dữ liệu.

---

## 2. KIẾN TRÚC 3 TẦNG AI CHUYÊN BIỆT
Chúng ta sử dụng 3 mô hình AI chuyên biệt để tối ưu hóa hiệu suất và chi phí:

1. **Gemini Flash (qua OpenRouter):** Đảm nhiệm NLU (Hiểu ngôn ngữ tự nhiên), viết lại câu hỏi (Query Rewriting), chặn câu hỏi rác (Guardrail) và tóm tắt báo cáo insight.
2. **Cohere `embed-multilingual-v3.0` (API):** Đảm nhiệm Embedding. Chuyển đổi Schema Database và câu hỏi người dùng thành Vector để tìm kiếm (Schema RAG). Rất mạnh tiếng Việt.
3. **Groq Llama 3.3 70B:** Đảm nhiệm Text-to-SQL. Viết câu lệnh SQL siêu tốc và chính xác cao dựa trên Schema và ngữ cảnh được cung cấp.

---

## 3. LUỒNG XỬ LÝ (END-TO-END PIPELINE)

Quy trình chuẩn 12 bước từ khi User chat đến khi nhận báo cáo:

1. **User Request & API Gateway:** User gõ câu hỏi trên Streamlit, gửi xuống FastAPI.
2. **Security Engine:** Xác thực JWT từ Cookie -> Định danh vai trò -> Lấy ra luật RLS (VD: `Region = 'Miền Bắc'`).
3. **Conversation Manager:** Bốc 3-5 câu chat cũ từ `sessions.db` làm ngữ cảnh nối tiếp.
4. **NLU Engine (Gemini Flash):** 
   - *Guardrail:* Chặn câu rác.
   - *Query Rewriting:* Đọc ngữ cảnh để viết lại thành **"Câu hỏi toàn nghĩa"** (VD: *"Chi phí miền Nam là bao nhiêu?"*).
5. **LOCAL CACHE ENGINE:** Băm (Hash) **[Câu hỏi toàn nghĩa + Luật RLS]** đi tìm Cache. 
   - 🟢 HIT: Trả kết quả cũ ngay lập tức (0.01s). Dừng quy trình.
   - 🔴 MISS: Đi tiếp xuống các bước AI.
6. **Schema RAG (Cohere + ChromaDB):** Tìm kiếm và trích xuất cấu trúc Bảng/Cột (Schema) liên quan nhất.
7. **Auto Data Profiler:** Tự động quét DB, lấy các **Giá trị mẫu (Sample Data)** của các cột vừa tìm được (Giúp AI không viết sai chính tả dữ liệu).
8. **Text-to-SQL (Groq Llama 3.3):** AI đọc Schema + Giá trị mẫu + Luật RLS -> Viết ra lệnh SQL được bọc kín bảo mật.
9. **SQL Validation:** Chạy thử SQL, nếu lỗi cú pháp tự động đẩy lại cho Llama sửa (Tối đa 3 lần).
10. **Data Execution & Query Limiter:** Bắt buộc chèn thêm `LIMIT` để chặn "Bom dữ liệu" (Tràn RAM) -> Chạy SQL vào Fabric/SQLite -> Nhận về DataFrame.
11. **AI Analysis & Visualization:** Gemini nhận xét số liệu kết hợp thư viện Plotly vẽ biểu đồ tương tác.
12. **Streaming Output & Lưu trữ:** Bắn kết quả từng phần (Streaming) lên UI để User không phải đợi lâu. Lưu JSON biểu đồ vào `sessions.db` và ghi lịch sử vào `audit.db`.

---

## 4. CÁC MODULE CÔNG NGHỆ CỐT LÕI

### 4.1. Cơ sở dữ liệu nội bộ (SQLite) & Cookie
- **`sessions.db`:** Lưu trữ lịch sử chat theo từng User ID. Dù người dùng có F5 (Reload trang), lịch sử chat vẫn được bốc lại nguyên vẹn từ file này.
- **`audit.db`:** Lưu nhật ký truy vết bảo mật (Ai, hỏi gì, lúc nào).
- **Trình duyệt (Cookie):** Chứa thẻ thông hành JWT Token (thời hạn 8 tiếng). Không lưu bất kỳ dữ liệu công ty nào lên Cookie.

### 4.2. Bảo mật Phân Quyền (Row Level Security - RLS)
- **Phương pháp Prompt Engineering:** Hệ thống quản lý phân quyền qua file `roles.json`. Không sử dụng code can thiệp sâu vào SQL để tránh lỗi cú pháp.
- Khi gọi LLM, hệ thống tự động tiêm câu luật: *"BẮT BUỘC thêm điều kiện `Region = 'Miền Bắc'` vào mệnh đề WHERE"* vào thẳng System Prompt. Groq Llama sẽ tự động tuân thủ.

### 4.3. Schema RAG Engine (7 Kỹ Thuật Tối Ưu Enterprise)
Sử dụng **ChromaDB** lưu trữ cục bộ và **Cohere API** kết hợp Mô hình Local:
1. **Parent-Child Retrieval + Column Pruning:** Tìm trúng cột, kéo toàn bộ Bảng (Parent) lên nhưng TỰ ĐỘNG TỈA BỎ các cột rác/cột hệ thống để cứu Context Window của LLM.
2. **Virtual Relationship Mapping:** Không phụ thuộc FK vật lý của DB. Tự định nghĩa khóa ngoại ảo (`virtual_relationships.json`) để đảm bảo AI luôn biết cách JOIN chuẩn xác.
3. **Asymmetric Embedding + Local Fallback:** Ưu tiên dùng Cohere v3. Tự động chuyển qua mô hình Local (như `all-MiniLM`) nếu API bị quá tải hoặc rớt mạng.
4. **Adaptive Reranking:** Đặt ngưỡng tự tin (>90%). Nếu tìm trúng phóc thì bỏ qua Reranker (Cross-Encoder) để tiết kiệm 2 giây tốc độ.
5. **Targeted Data Profiling:** Chỉ tự động quét lấy mẫu giá trị (Sample Data) đối với các cột Low Cardinality (< 50 giá trị). Cấm quét các cột hàng triệu dòng.
6. **Auto-Tested Few-shot SQL:** Nhét các câu SQL mẫu vào Prompt, kết hợp Bot chạy ngầm kiểm thử ban đêm để loại bỏ các câu SQL mẫu đã bị lỗi thời do đổi schema.
7. **Semantic Synonyms Dictionary:** Dùng file `synonyms.json` ("Chốt đơn" = "Completed_Orders") để làm phao cứu sinh cho những từ lóng, viết tắt nội bộ mà AI không thể Semantic Search được.

### 4.4. Multi-Connector (Factory Pattern)
- Code hỗ trợ chuyển đổi linh hoạt giữa SQLite (Test máy cá nhân), PostgreSQL và Microsoft Fabric SQL Endpoint (Production) chỉ bằng 1 dòng thiết lập trong `.env`.

---

## 5. LỘ TRÌNH TRIỂN KHAI (5 CHẶNG)

| Chặng | Tên Chặng | Nội dung chính | Trạng Thái |
|:---:|:---|:---|:---:|
| **1** | **Foundation & Core** | Khởi tạo cấu trúc dự án, config `.env`, logger, quản lý lỗi, kết nối OpenRouter (Gemini, Llama). | ✅ Hoàn Thành |
| **2** | **Data Source & Cache** | Viết Connectors (SQLite, Fabric, Postgres), hệ thống Cache, tạo kiến trúc DB `sessions.db` & `audit.db`. | ✅ Hoàn Thành |
| **3** | **AI Engines (Bộ Não)** | Code luồng NLU (Rewriting + Guardrail), Schema RAG (7 kỹ thuật), Text-to-SQL, SQL Validation. | ⏳ Đang triển khai |
| **4** | **Orchestrator** | Bọc 12 bước xử lý vào LangChain/LangGraph. Tích hợp Security Engine (RLS Prompt). | 🔜 Sắp tới |
| **5** | **UI & API** | Code API Backend (FastAPI). Code giao diện Chatbot Streamlit. Cơ chế đăng nhập JWT & Cookie. | 🔜 Sắp tới |
