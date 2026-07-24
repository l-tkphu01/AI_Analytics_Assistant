# 📊 BẢNG THEO DÕI TIẾN ĐỘ DỰ ÁN AI ANALYTICS ASSISTANT
> Cập nhật lần cuối: 2026-07-23 20:43

---

## ✅ GIAI ĐOẠN 1: HẠ TẦNG NỀN TẢNG (INFRASTRUCTURE) — HOÀN THÀNH

| File | Trạng thái | Ghi chú |
|------|-----------|---------|
| `config/settings.py` | ✅ Xong | Cấu hình Pydantic, đọc `.env` |
| `config/database.py` | ✅ Xong | Khởi tạo sessions.db, audit.db, business_mock.db |
| `core/logger.py` | ✅ Xong | Hệ thống Log tập trung |
| `core/models.py` | ✅ Xong | UserContext, QueryResult, các model dữ liệu |
| `core/exceptions.py` | ✅ Xong | Custom Exception classes |
| `core/cache.py` | ✅ Xong | Bộ nhớ đệm LRU Cache |
| `core/llm_providers.py` | ✅ Code xong | 6 hàm kết nối AI (Gemini, Groq, Cohere, HuggingFace). **Chưa test được vì chưa cài thư viện + chưa có API Key** |
| `modules/data_source/base.py` | ✅ Xong | Abstract class DataConnector |
| `modules/data_source/sqlite_source.py` | ✅ Xong | SQLiteConnector + 3 bảng dữ liệu mẫu (Sales, Customers, Products) |
| `main.py` | ✅ Xong | FastAPI app + API Login + API Query (đã gắn Security) |

---

## ✅ GIAI ĐOẠN 2: SECURITY ENGINE — HOÀN THÀNH 90%

### Đã hoàn thành ✅

| File | Trạng thái | Ghi chú |
|------|-----------|---------|
| `modules/security/auth.py` | ✅ Xong | JWT Token: tạo, xác thực, mock_login, đọc roles.yaml |
| `modules/security/rbac.py` | ✅ Xong | Bảo mật cấp Bảng (Table). Tự quét Database lấy danh sách bảng (Dynamic Schema) |
| `modules/security/rls.py` | ✅ Xong | Bảo mật cấp Dòng (Row). Sinh Prompt RLS + Validate SQL |
| `modules/security/guardrails.py` | ✅ Tầng 1 xong | Tầng 1 (Rule-based từ YAML): Hoạt động 100%. Tầng 2 (AI Semantic): Code sẵn, **chờ Giai đoạn 3 cài thư viện AI mới "sống"** |
| `config/roles.yaml` | ✅ Xong | Phân quyền ABAC: admin, manager_north, manager_south, viewer |
| `config/security_guard.yaml` | ✅ Xong | Từ cấm, SQL Injection, Business Safe Phrases, AI Guardrail Prompt, Query Limits |

### Chưa hoàn thành ⏳

| File | Trạng thái | Sẽ làm ở Giai đoạn nào | Ghi chú |
|------|-----------|------------------------|---------|
| `modules/security/audit.py` | ⏳ Chưa code | **Giai đoạn 3** | Lưu nhật ký truy vấn (Audit Trail). Cần có AI chạy mới có dữ liệu để ghi log |
| `modules/security/cls.py` | ⏳ Chưa code | **Giai đoạn 4** | Column-Level Security. Tự quét Database phát hiện cột nhạy cảm (thay vì hardcode YAML) |
| `mock_login` nâng cấp | ⏳ Chưa sửa | **Giai đoạn 4** | Đổi từ code cứng `if "nam"` sang Dropdown đọc từ roles.yaml |
| Guardrails Tầng 2 | ⏳ Code xong, chưa test | **Giai đoạn 3** | Chờ cài `langchain-openai` + điền API Key |

---

## ⏳ GIAI ĐOẠN 3: XÂY NÃO AI (CORE AI) — CHƯA BẮT ĐẦU

| File | Trạng thái | Thứ tự | Nhiệm vụ |
|------|-----------|--------|----------|
| `modules/schema/engine.py` | ⏳ Chưa code | 1️⃣ | Đọc cấu trúc Database (Bản đồ cho AI) |
| `modules/schema/indexer.py` | ⏳ Chưa code | 2️⃣ | Embedding Schema vào ChromaDB (Vector Search) |
| `modules/nlu/engine.py` | ⏳ Chưa code | 3️⃣ | Hiểu câu hỏi Tiếng Việt (Intent + Entity) |
| `modules/sql/generator.py` | ⏳ Chưa code | 4️⃣ | Sinh câu SQL từ ngôn ngữ tự nhiên (Text-to-SQL) |
| `modules/sql/validator.py` | ⏳ Chưa code | 5️⃣ | Kiểm tra SQL hợp lệ + phối hợp RBAC/RLS |
| `modules/sql/self_correction.py` | ⏳ Chưa code | 6️⃣ | Tự sửa SQL khi chạy lỗi (tối đa 3 lần) |
| `config/prompts.yaml` | ⏳ Chưa tạo | — | Tất cả Prompt dạy AI (thay thế file .txt rời rạc) |
| `config/model_params.yaml` | ⏳ Chưa tạo | — | Tham số AI: temperature, model name, token limit |
| `.env` | ⏳ Chưa điền Key | — | Cần điền: OPENROUTER_API_KEY, GROQ_API_KEY, COHERE_API_KEY |
| Cài thư viện AI | ⏳ Chưa cài | — | `pip install langchain-openai langchain-groq langchain-cohere langchain-community` |

---

## ⏳ GIAI ĐOẠN 4: ĐÁNH BÓNG & HOÀN THIỆN — CHƯA BẮT ĐẦU

| Hạng mục | Trạng thái | Ghi chú |
|----------|-----------|---------|
| Giao diện Streamlit (UI) | ⏳ | Trang đăng nhập, Chat, Dashboard biểu đồ |
| `cls.py` - Auto-detect cột nhạy cảm | ⏳ | Quét Database tự động thay vì hardcode YAML |
| `mock_login` → Dynamic Login | ⏳ | Dropdown chọn Role từ roles.yaml |
| `audit.py` → Xuất báo cáo Kiểm toán | ⏳ | Export PDF/Excel lịch sử truy vấn |
| Guardrails Tầng 2 Fine-tuning | ⏳ | Tinh chỉnh Prompt AI sau khi test thực tế |
| Deploy lên Render/Railway | ⏳ | Triển khai Cloud |

---

## 📌 DANH SÁCH "MÓN NỢ KỸ THUẬT" (Technical Debt)

> Những thứ tạm bợ cần quay lại sửa trước khi nộp đồ án:

1. ⚠️ `sensitive_columns` trong YAML đang hardcode tên cột không khớp Database thật → Chờ `cls.py` tự quét
2. ⚠️ `mock_login` đang code cứng 3 tài khoản → Chờ Giai đoạn 4 nâng cấp
3. ⚠️ `main.py` dòng 75 đang dùng `fake_sql_from_ai` giả lập → Chờ Giai đoạn 3 thay bằng AI thật
4. ⚠️ File `roles.json` cũ vẫn còn tồn tại → Có thể xóa đi (hệ thống đã dùng `roles.yaml`)
