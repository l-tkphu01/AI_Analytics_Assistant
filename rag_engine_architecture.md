# 🧠 Kiến Trúc Schema RAG & Cơ Chế Bảo Vệ (Enterprise Edition)
*Tài liệu phân tích chuyên sâu về 7 kỹ thuật Retrieval-Augmented Generation (RAG) và Chốt chặn an toàn Query Limiter của hệ thống AI Analytics.*

---

## 1. TẠI SAO CẦN SCHEMA RAG NÂNG CAO?

Trong kiến trúc Text-to-SQL, nếu quăng toàn bộ cấu trúc Database (Schema) cho AI, bộ nhớ (Context Window) sẽ bị quá tải, AI sẽ bị "ảo giác" (Hallucination) và sinh ra SQL sai. 
Mục tiêu của **Schema RAG Engine** là chỉ bốc chính xác 1-2 cái Bảng và vài cái Cột thực sự liên quan đến câu hỏi của User để làm mồi cho AI. Tuy nhiên, RAG cơ bản vướng rất nhiều lỗi thực tế. Dưới đây là **7 Kỹ thuật vá lỗi chuẩn Enterprise**.

---

## 2. BỘ 7 KỸ THUẬT SCHEMA RAG TỐI ƯU

### 2.1. Parent-Child Retrieval & Tỉa Cột (Column Pruning)
- **Vấn đề:** RAG cơ bản nhúng nguyên cả Bảng (100 cột) thành 1 Vector. Tìm rất thiếu chính xác. Còn nếu nhúng từng Cột, khi tìm trúng 1 Cột thì AI lại không thấy các cột xung quanh để viết lệnh.
- **Giải pháp:** Nhúng riêng lẻ từng Cột (Child) để tìm kiếm cực nhạy. Khi tìm trúng, móc cả Bảng (Parent) lên. 
- **Tỉa Cột (Bảo vệ RAM):** Trước khi đưa Bảng (Parent) cho AI, hệ thống chạy màng lọc cắt bỏ ngay các cột "Rác" (Cột Description dài, cột Audit `created_by`, cột Password). Chỉ đưa cho AI Cột Khóa (PK/FK), Cột Số liệu (Metrics) và Cột Vừa tìm trúng.

### 2.2. Khóa Ngoại Ảo (Virtual Relationship Mapping)
- **Vấn đề:** Data Warehouse (như Microsoft Fabric) thường không khai báo Foreign Key (Khóa ngoại) vật lý. AI sẽ không biết đường dùng lệnh `JOIN` giữa 2 bảng.
- **Giải pháp:** Kỹ sư tạo ra file `virtual_relationships.json`. File này do kỹ sư hoặc script tự động khai báo rành mạch: *"Bảng Orders nối với Customers qua CustomerID"*. Hệ thống sẽ dùng file này ép AI phải nối bảng cho đúng, thoát khỏi sự phụ thuộc vào Database gốc.

### 2.3. Nhúng Dự Phòng (Asymmetric Embedding + Local Fallback)
- **Vấn đề:** Dùng Cohere v3 API miễn phí rất dễ dính lỗi Rate Limit (Quá tải).
- **Giải pháp:** Hệ thống được thiết kế với cơ chế "Lốp dự phòng". Bình thường dùng Cohere v3. Nếu Cohere rớt mạng, Code Python tự động chuyển hướng sang mô hình `all-MiniLM-L6-v2` chạy Offline trên máy chủ (chỉ nặng 80MB, siêu nhẹ). Hệ thống bất tử 24/7.

### 2.4. Rerank Có Điều Kiện (Adaptive Reranking)
- **Vấn đề:** Chấm điểm chéo (Cross-Encoder / Reranker) rất chính xác nhưng làm chậm hệ thống mất 1-2 giây.
- **Giải pháp:** Đặt ngưỡng tự tin (Confidence Threshold). ChromaDB ban đầu sẽ vớt lên **Top 10 kết quả**. 
  - Nếu kết quả Top 1 có độ chính xác **> 90%** (User gọi đúng tên cột), hệ thống **bỏ qua Reranker**, bốc thẳng 1-3 kết quả cao nhất đưa cho Llama để tiết kiệm 2 giây. 
  - Nếu kết quả < 90% (Câu hỏi mơ hồ), hệ thống mới kích hoạt Reranker để chấm điểm lại Top 10 này, sau đó chắt lọc ra đúng **Top 3 kết quả xuất sắc nhất** gửi cho Llama.

### 2.5. Quét Mẫu Có Chọn Lọc (Targeted Data Profiling)
- **Vấn đề:** AI hay viết sai chính tả có dấu/không dấu (Ví dụ viết `Cancelled` thay vì `Đã hủy`). Nếu cho hệ thống quét lấy mẫu (Sample Data) nhét vào Prompt thì lại sợ quét nhầm cột Tên người (có 1 triệu dòng) làm nổ tung Prompt.
- **Giải pháp:** Hệ thống kiểm tra trước. Cột nào đếm có **< 50 giá trị** (Low Cardinality - Dạng danh mục) thì quét lấy mảng giá trị nhét vào Prompt. Cột nào > 50 thì giấu đi. 
- **Đặc biệt với cột > 50:** RAG sẽ phân tích thêm "Kiểu dữ liệu". Nếu là kiểu Số/Ngày tháng (`DECIMAL, TIMESTAMP`), AI vẫn dùng toán tử Toán học bình thường (`=, >, <`). Nhưng nếu là kiểu Chữ (`VARCHAR, TEXT`), hệ thống mới kích hoạt "Luật Thép": ép AI dùng toán tử `ILIKE '%...%'` thay cho dấu `=` để chống sai chính tả.


### 2.6. Phao Cứu Sinh Tự Động (Auto-Tested Few-shot SQL)
- **Vấn đề:** Lưu 10 câu SQL mẫu khó (Few-shot) vào kho để AI bắt chước. Nhưng năm sau đổi cấu trúc DB, 10 câu này sai, AI copy theo sai bét nhè.
- **Giải pháp:** Cài Cron-job chạy ngầm ban đêm. Tự động lấy 10 câu SQL mẫu này ném vào Database chạy thử. Câu nào báo lỗi Syntax -> Tự động xóa khỏi kho học tập của AI.

### 2.7. Từ Điển Tiếng Lóng (Semantic Synonyms)
- **Vấn đề:** User hay dùng tiếng lóng / viết tắt (Ví dụ: "Chốt đơn", "Doanh số - DS"). Semantic Search trên mô hình tiếng Anh sẽ không hiểu để map vào cột `Completed_Orders` hay `Revenue`.
- **Giải pháp:** Tạo file `synonyms.json`. Khi User hỏi, code Python sẽ dùng file này dịch "Chốt đơn" thành "Completed Orders" TRƯỚC KHI đem đi nhúng Vector. AI lập tức hiểu và map trúng cột 100% mà không cần phải tốn ngàn Đô-la để Train lại (Fine-tune) mô hình nhúng.

---

## 3. CHỐT CHẶN BẢO VỆ "BOM DỮ LIỆU" (QUERY LIMITER)

Ở **Bước 10** trong Pipeline (Data Execution), có một rủi ro chí mạng khiến Server của bạn sập nguồn.

### 3.1. Rủi ro (Out of Memory - OOM)
- User gõ cộc lốc: *"Cho xem đơn hàng"*.
- AI viết SQL chuẩn: `SELECT * FROM Orders`.
- Nếu Bảng Orders có **5 triệu dòng** (Nặng khoảng 3GB), code Python sẽ cố gắng kéo toàn bộ 3GB này nhét vào RAM của máy chủ FastAPI (Gói miễn phí chỉ có 512MB RAM).
- **Hậu quả:** Máy chủ quá tải RAM, Crash (Sập nguồn) ngay lập tức.

### 3.2. Cơ chế "Phanh Tay Điện Tử"
Để chống lại thảm họa này, ngay trước khoảnh khắc gửi câu SQL xuống Database, hệ thống có một lớp chặn bằng Code Python (Regex/Sqlglot):
1. **Phân tích:** Nó soi xem câu lệnh SQL là dạng Tổng hợp (Có `SUM, COUNT, GROUP BY`) hay dạng Lấy dữ liệu thô (Có `SELECT *`).
2. **Ép giới hạn:** Nếu là dữ liệu thô và AI quên viết chữ `LIMIT`, hệ thống **bắt buộc dán thêm chữ `LIMIT 100`** vào đuôi câu SQL.
3. **Hiển thị khéo léo:** Kéo 100 dòng về an toàn, hiển thị lên UI kèm câu nhắc mờ: *"Để bảo vệ tốc độ hệ thống, chỉ 100 dòng đầu tiên được hiển thị. Vui lòng đặt câu hỏi cụ thể hơn nếu cần xem tiếp."*
