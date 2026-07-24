# ⚡ Kiến Trúc Bộ Nhớ Đệm (Local Cache Engine)
*Tài liệu thiết kế chi tiết về cơ chế tiết kiệm API, tối ưu tốc độ và giảm tải Database cho AI Analytics Assistant.*

---

## 1. TỔNG QUAN (OVERVIEW)

Trong hệ thống Data Analytics bằng AI, có những câu hỏi mang tính chất lặp đi lặp lại rất cao. Ví dụ, vào buổi sáng, giám đốc và các trưởng phòng đều đăng nhập và hỏi chung một câu: *"Cập nhật doanh thu tổng của tháng này"*.

Nếu không có Cache, hệ thống sẽ phải chạy lại quy trình 12 bước nặng nề:
1. Gọi API LLM để dò Schema.
2. Gọi LLM để viết SQL.
3. Chạy lệnh SQL vào Database Microsoft Fabric (tốn Compute).
4. Gọi LLM để viết báo cáo.

**Nhiệm vụ của Local Cache Engine là:** Chặn đứng quy trình này nếu câu hỏi đó đã có người hỏi rồi. Nó giúp trả về kết quả trong **0.01 giây** và tiết kiệm **100% chi phí API & Compute**.

---

## 2. KỸ THUẬT NHẬN DIỆN CÂU HỎI TRÙNG (HASHING MECHANISM)

Làm sao để hệ thống biết 2 câu hỏi là "giống nhau" một cách cực nhanh? Hệ thống sử dụng thuật toán Băm (Hashing) kết hợp Phân Quyền.

### Công thức tạo Cache Key:
Hệ thống kết hợp 2 yếu tố: **[Câu hỏi của người dùng] + [Quyền hạn RLS của họ]**.

- **Ví dụ 1 (Cùng quyền):**
  - Trưởng phòng A (Miền Bắc) hỏi: *"Doanh thu bao nhiêu?"* ➡️ Mã băm: `hash("Doanh thu bao nhiêu?" + "Region='Miền Bắc'")` = **ABC_123**
  - Hôm sau, Trưởng phòng B (CŨNG là Miền Bắc) hỏi: *"Doanh thu bao nhiêu?"* ➡️ Trùng mã băm **ABC_123** ➡️ **(CACHE HIT - Trả kết quả ngay!)**

- **Ví dụ 2 (Khác quyền - Cực kỳ quan trọng để bảo mật):**
  - Trưởng phòng C (Miền Nam) hỏi: *"Doanh thu bao nhiêu?"* ➡️ Mã băm: `hash("Doanh thu bao nhiêu?" + "Region='Miền Nam'")` = **XYZ_999**
  - Vì mã băm khác nhau, Trưởng phòng Nam sẽ **KHÔNG BAO GIỜ** vô tình lấy nhầm cục Cache doanh thu của Miền Bắc.

---

## 3. LUỒNG HOẠT ĐỘNG (CACHE WORKFLOW)

Cơ chế hoạt động tuân theo chuẩn **Read-Through Cache**:

1. **Giai đoạn Đọc (Read):**
   - User gõ câu hỏi ➡️ Hệ thống tạo mã Hash.
   - Tìm mã Hash trong kho Cache.
   - 🟢 **Nếu Tồn tại (Hit):** Lấy Dataframe (bảng số liệu) + Biểu đồ cũ trả về ngay lập tức. Dừng toàn bộ luồng AI.
   - 🔴 **Nếu Không tồn tại (Miss):** Cho qua. Hệ thống gọi AI và Database Fabric chạy như bình thường.

2. **Giai đoạn Ghi (Write):**
   - Sau khi AI và Fabric chạy xong, hệ thống gói toàn bộ kết quả (Bảng Dataframe + Lời nhận xét + Biểu đồ Plotly) thành một file JSON.
   - Gắn mã Hash làm tên file và cất vào kho Cache để phục vụ những người đến sau.

---

## 4. CHIẾN LƯỢC LƯU TRỮ ZERO-COST (STORAGE STRATEGY)

Trong giai đoạn R&D, chúng ta ưu tiên chiến lược "Zero-Cost" nên sẽ **không dùng Redis** (dù Redis là chuẩn công nghiệp cho Cache). Thay vào đó, chúng ta dùng phương pháp lưu trữ cục bộ:

### Lưu trữ bằng File (File-based JSON Cache)
- **Vị trí:** Lưu tại thư mục `data/query_cache/` trên ổ cứng ảo của Server Render.
- **Cấu trúc:** Mỗi câu hỏi lưu thành 1 file: `cache_ABC_123.json`.
- **Nội dung:** Chứa dữ liệu Dataframe (chuyển sang dạng text) và cấu hình biểu đồ.

### Cơ chế tự hủy (TTL - Time To Live)
Dữ liệu phân tích (Analytics) cần phải luôn cập nhật mới. Do đó, Cache sẽ được gài mìn hẹn giờ:
- **Thời gian sống mặc định:** **5 Phút (300 giây)**.
- Quá 5 phút, file Cache sẽ tự bị đánh dấu là "Hết hạn" (Stale).
- Nếu User hỏi lại câu đó, hệ thống sẽ ép chạy lại DB Fabric để lấy số liệu mới nhất (Real-time).

---

## 5. LỢI ÍCH KÉP TỪ KIẾN TRÚC NÀY

1. **Bảo vệ Limit của LLM miễn phí:** Các gói Free của Gemini (15 req/phút) hay Groq (30 req/phút) sẽ không bao giờ bị quá tải (Rate Limit Hit) nhờ Cache chặn bớt traffic thừa.
2. **Tiết kiệm tiền cho Server Microsoft Fabric:** Fabric tính tiền theo Capacity Units (Compute). Chặn được truy vấn thừa đồng nghĩa với việc doanh nghiệp tiết kiệm được hàng ngàn đô la chi phí vận hành Data Warehouse mỗi tháng.
