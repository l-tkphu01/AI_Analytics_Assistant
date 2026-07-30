# KẾ HOẠCH TRIỂN KHAI GIAI ĐOẠN 3: XÂY DỰNG BỘ NÃO AI (CORE AI PIPELINE)

Giai đoạn 3 là **trái tim** của toàn bộ dự án. Biến hệ thống từ một API bảo mật "rỗng ruột" thành một **Trợ lý AI phân tích dữ liệu tự chủ** — có thể hiểu câu hỏi tiếng Việt, tự sinh SQL, tự sửa lỗi, và trả dữ liệu chính xác cho người dùng.

Toàn bộ thiết kế tuân theo **Bộ 7 Kỹ thuật Advanced Schema RAG (Enterprise Edition)** đã được chuẩn hóa trong file `rag_engine_architecture.md`.

---

## ✅ BƯỚC 0: THIẾT LẬP MÔI TRƯỜNG — ĐÃ HOÀN THÀNH 100%

| Hạng mục | Trạng thái | Ghi chú |
|---|---|---|
| Cài thư viện `langchain-openai`, `langchain-groq`, `langchain-cohere` | ✅ Xong | Đã kiểm tra bằng `pip show` |
| Khai báo API Keys trong `.env` | ✅ Xong | `OPENROUTER_API_KEY`, `GROQ_API_KEY`, `COHERE_API_KEY` |
| `config/model_params.yaml` | ✅ Xong | Cấu hình 7 model AI (Config-Driven) |
| `config/prompts.yaml` | ✅ Xong | Tập hợp 3 System Prompt (NLU, Text-to-SQL, Self-Correction) |
| `core/llm_providers.py` (Config-Driven) | ✅ Xong | Đọc tham số từ `model_params.yaml`, không còn hardcode |

---

## 🧠 BỘ 7 KỸ THUẬT ADVANCED SCHEMA RAG SẼ TRIỂN KHAI

> Tham chiếu từ file: `rag_engine_architecture.md`

| # | Tên kỹ thuật | Vấn đề giải quyết | Module phụ trách |
|---|---|---|---|
| **1** | **Parent-Child Retrieval & Column Pruning** | RAG cơ bản nhúng cả Bảng → thiếu chính xác. Giải pháp: Nhúng từng Cột (Child), tìm trúng thì móc cả Bảng (Parent) lên, nhưng tỉa bớt cột rác trước khi đưa cho AI | `modules/schema/indexer.py` & `engine.py` |
| **2** | **Virtual Relationship Mapping** | Data Warehouse không có FK vật lý → AI không biết JOIN. Giải pháp: File `virtual_relationships.json` khai báo rõ quan hệ giữa các bảng | `config/virtual_relationships.json` & `engine.py` |
| **3** | **Local Embedding Fallback** | Cohere API rớt mạng/Rate Limit. Giải pháp: Tự động chuyển sang mô hình offline `all-MiniLM-L6-v2` | `core/llm_providers.py` *(Đã code ở GĐ 1)* |
| **4** | **Adaptive Reranking** | Reranker chính xác nhưng chậm 1-2s. Giải pháp: Score Top 1 > 90% → bỏ qua Reranker. Score < 90% → bật Cohere Rerank v3 lọc Top 3 | `modules/schema/indexer.py` |
| **5** | **Targeted Data Profiling** | AI hay viết sai chính tả ("Cancelled" thay vì "Đã hủy"). Giải pháp: Cột < 50 giá trị → nhét mẫu vào Prompt. Cột text > 50 → ép AI dùng `ILIKE '%...%'` | `modules/schema/engine.py` |
| **6** | **Auto-Tested Few-shot SQL** | Câu SQL mẫu bị lỗi khi DB đổi cấu trúc. Giải pháp: Chạy ngầm test lại các câu mẫu, tự xóa câu hỏng | `modules/sql/generator.py` |
| **7** | **Semantic Synonyms Dictionary** | Tiếng lóng ("chốt đơn", "doanh số") mô hình tiếng Anh không hiểu. Giải pháp: File `synonyms.json` dịch trước khi Vector Search | `config/synonyms.json` & `modules/nlu/engine.py` |
| **+** | **Query Limiter (Phanh tay)** | `SELECT *` trên bảng 5 triệu dòng → nổ RAM server. Giải pháp: Tự dán `LIMIT 100` nếu AI quên | `modules/sql/validator.py` |

---

## 📐 THỨ TỰ TRIỂN KHAI (IMPLEMENTATION ORDER)

> [!IMPORTANT]
> Phải làm **đúng thứ tự** vì các module có phụ thuộc lẫn nhau (Dependencies): DataConnector phải được nâng cấp trước để Schema Engine có interface chuẩn mà gọi.

```
Bước 0.5 ──► Bước 1 ──► Bước 2 ──► Bước 3 ──► Bước 4 ──► Bước 5 ──► Bước 6 ──► Bước 7
Nâng cấp     Schema      Schema     NLU        SQL         SQL         SQL         Tích hợp
DataConnector Engine      Indexer    Engine     Generator   Validator   Self-Fix    main.py
```

---

### 🔧 BƯỚC 0.5: NÂNG CẤP KIẾN TRÚC DataConnector — TỰ NHẬN DIỆN DATABASE

> [!CAUTION]
> **Đây là bước quan trọng nhất!** Nếu không làm bước này, toàn bộ hệ thống sẽ bị "gắn cứng" vào SQLite. Khi đổi sang PostgreSQL hoặc Fabric, phải sửa lại hàng loạt file.

**Vấn đề hiện tại:** `DataConnector` (base class) chỉ có 5 method cơ bản (`connect`, `execute`, `get_schema`, `test_connection`, `get_dialect`). Thiếu các method mà Schema Engine cần gọi.

**Giải pháp:** Bổ sung thêm 2 abstract method mới vào `DataConnector`. Mỗi Connector (SQLite, PostgreSQL, Fabric) sẽ tự implement theo cách riêng của mình.

#### [MODIFY] `modules/data_source/base.py` (Abstract Base Class)
Thêm 2 abstract method mới:
- `get_foreign_keys()` → Trả về danh sách quan hệ FK giữa các bảng.
- `get_sample_values(table, column, limit=50)` → Trả về mảng giá trị mẫu của 1 cột (cho Data Profiling).

#### [MODIFY] `modules/data_source/sqlite_source.py`
Implement 2 method mới cho SQLite:
- `get_foreign_keys()`: Dùng `PRAGMA foreign_key_list(table)` để quét FK.
- `get_sample_values()`: Dùng `SELECT DISTINCT column FROM table LIMIT 50`.

**Kết quả:** Sau bước này, `schema/engine.py` chỉ cần gọi `connector.get_foreign_keys()` — nó **KHÔNG CẦN BIẾT** bên dưới là SQLite (dùng `PRAGMA`) hay PostgreSQL (dùng `information_schema`). Khi nào sếp code thêm `PostgresConnector` hoặc `FabricConnector`, chỉ cần implement 2 method đó theo cách riêng là toàn bộ hệ thống chạy ngon!

---

### 🔧 BƯỚC 1: Schema Engine — Bản đồ Database cho AI
#### [NEW] `config/virtual_relationships.json` *(Chỉ dùng làm DỰ PHÒNG)*
- File này chỉ được đọc khi Auto-Detect không tìm thấy quan hệ nào (ví dụ: Data Warehouse không có FK, 2 bảng đặt tên cột khác nhau).
- **Kỹ thuật RAG #2: Virtual Relationship Mapping.**

#### [NEW] `modules/schema/engine.py`
- Hàm `get_full_schema()`: Gọi `SQLiteConnector.get_schema()` lấy toàn bộ Bảng + Cột.
- Hàm `prune_columns(schema)`: **Kỹ thuật RAG #1 (Column Pruning)** — Cắt tỉa cột rác (`created_by`, `password`...), chỉ giữ PK/FK + Metrics.
- Hàm `profile_columns(schema)`: **Kỹ thuật RAG #5 (Targeted Data Profiling)** — Đếm giá trị từng cột. Cột < 50 values → nhét mẫu vào Prompt. Cột text > 50 → ghi chú "dùng ILIKE".
- Hàm `detect_relationships()`: **ĐỀ XUẤT MỚI — Auto-Detect Gộp 3 Lớp (Tránh bỏ sót):**
  - Hàm này sẽ chạy CẢ 3 lớp dưới đây và **GỘP (Union)** tất cả kết quả lại để có bức tranh quan hệ đầy đủ nhất:
  - **Lớp 1 — SQLite/PostgreSQL:** Quét FK từ metadata Database (`PRAGMA foreign_key_list` / `information_schema`).
  - **Lớp 2 — Naming Convention (Kèm Luật Thép):** Quét tên cột trùng nhau giữa các bảng. **Luật Thép:** Chỉ ghép quan hệ nếu tên cột chứa các từ khóa định danh (`ID`, `Code`, `Key`) để chống ghép nhầm cột vô thưởng vô phạt (như `Name`, `Status`).
  - **Lớp 3 — JSON Fallback:** Đọc file `virtual_relationships.json` để nhặt thêm các quan hệ đặc thù do kỹ sư tự cấu hình.
- Hàm `format_schema_for_prompt()`: Gom tất cả (Schema + Quan hệ + Data Profiling) thành 1 chuỗi Text tối ưu để mớm vào Prompt cho AI.

---

### 🔧 BƯỚC 2: Schema Indexer — Vector Search bằng ChromaDB
#### [NEW] `modules/schema/indexer.py`
- Hàm `index_schema()`: **Kỹ thuật RAG #1 (Parent-Child)** — Nhúng từng Cột (Child) thành vector riêng lẻ vào ChromaDB. Metadata của mỗi vector ghi rõ cột đó thuộc Bảng (Parent) nào.
- Hàm `search_relevant_tables(question)`: Tìm Top 10 cột liên quan, rồi móc Parent (Bảng) lên.
- Hàm `adaptive_rerank(results)`: **Kỹ thuật RAG #4 (Adaptive Reranking)** — Nếu Score Top 1 > 90% → trả luôn. Nếu < 90% → gọi Cohere Rerank v3 lọc Top 3.
- Xử lý **Kỹ thuật RAG #3 (Local Fallback)**: Nếu Cohere Embedding lỗi → tự động chuyển sang `get_fallback_embedding_model()`.

---

### 🔧 BƯỚC 3: NLU Engine — Hiểu câu hỏi Tiếng Việt

#### ⚠️ QUYẾT ĐỊNH THIẾT KẾ QUAN TRỌNG:
- **BỎ** file `config/synonyms.json` (Không cần từ điển thủ công).
  - Lý do 1: `schema_config.yaml` đã chứa từ đồng nghĩa Việt-Anh (do LLM Auto-Documenter sinh).
  - Lý do 2: Gemini Flash đủ thông minh để hiểu tiếng lóng trực tiếp trong lúc phân tích intent.
- **BỎ** hàm `preprocess_question()` (Không cần bước tiền xử lý riêng).

#### 🔍 3 ĐIỂM CHÊ ĐÃ ĐƯỢC VÁ TRONG THIẾT KẾ:
1. **NLU có thừa không?** → Giữ lại vì NLU giúp Vector Search chính xác hơn + Dễ Debug (nhìn JSON là biết AI hiểu đúng/sai).
2. **NLU không biết DB có gì → Bịa tên cột!** → Vá bằng cách nhồi danh sách tên Bảng + Cột vào Prompt, ép Gemini chỉ được chọn từ danh sách có sẵn.
3. **Tốn thêm 1 lần gọi API (chậm + tốn tiền)** → Vá bằng cách chạy NLU **song song** với Vector Search thay vì nối tiếp.

#### 🔄 KIẾN TRÚC CHẠY (Đã tối ưu):
```
Câu hỏi User ("Còn Samsung thì sao?")
     │
     ▼
[1. Guardrails] ← Lưới Lọc Kép (Tầng 1: Rule-based + Tầng 2: AI Semantic)
     │              Nếu rác/độc hại → DỪNG LUỒNG, trả lỗi cho User
     ▼
[2. Rewriting]  ← Đọc lịch sử chat, viết lại câu hỏi cho đầy đủ
     │              "Còn Samsung thì sao?" → "Doanh thu Samsung bao nhiêu?"
     ▼
Câu hỏi an toàn + đầy đủ
     │
     ├──────────────────┐
     ▼                  ▼
[3. Vector Search] [4. NLU Engine]      ← Chạy SONG SONG (tiết kiệm thời gian)
   (Tìm bảng)     (Bóc intent+filter)
     │                  │
     └────────┬─────────┘
              ▼
      [5. SQL Generator]
    (Nhận cả Schema + NLU JSON → Sinh SQL chuẩn)
```

#### [NEW] `modules/nlu/engine.py`
- Hàm `rewrite_question(question, chat_history)`:
  - Input: Câu hỏi hiện tại + Lịch sử chat gần nhất (tối đa 3 lượt).
  - Xử lý 2 trường hợp:
    - **Follow-up**: "Còn Samsung?" → "Doanh thu Samsung bao nhiêu?" (dựa vào ngữ cảnh chat trước).
    - **Viết tắt/Lóng**: "DT Q3 bn?" → "Doanh thu quý 3 bao nhiêu?"
  - Nếu câu hỏi đã rõ ràng → Giữ nguyên, không sửa bậy.
  - Fallback: Nếu Gemini lỗi → Trả lại câu gốc nguyên vẹn.

- Hàm `analyze_intent(question, schema_columns)`:
  - Input: Câu hỏi tiếng Việt + Danh sách tên bảng/cột từ DB (để Gemini không bịa).
  - Gọi **Gemini Flash Lite** (qua `LLMProvider.get_nlu_llm()`, siêu rẻ ~0.5s).
  - Output: JSON chuẩn gồm:
    ```json
    {
        "intent": "RANKING | AGGREGATION | COMPARISON | TREND | DETAIL | GENERAL",
        "metric": "SalesAmount",
        "dimension": "ProductName",
        "filter": {"Brand": "Apple"},
        "time_range": {"quarter": 3},
        "limit": 5,
        "sort": "DESC"
    }
    ```
  - Xử lý Fallback: Nếu Gemini trả JSON lỗi → Trả về intent mặc định `GENERAL` để pipeline không bị chết.

#### ⚙️ QUYẾT ĐỊNH KỸ THUẬT: Prompt tách ra file YAML
- Tất cả prompt của NLU (`nlu_intent_prompt`, `nlu_rewrite_prompt`) đều nằm trong `config/prompts.yaml`.
- Không hardcode prompt trong code Python. Muốn sửa cách AI phân tích → Chỉ cần sửa file YAML.

#### [NEW] `tests/test_nlu.py`
- Test với 5 câu hỏi tiếng Việt đa dạng (AGGREGATION, RANKING, COMPARISON, TREND, DETAIL).
- Test Rewriting với câu follow-up + viết tắt.
- Test Fallback khi không có schema.

---

### 🔧 BƯỚC 4: SQL Generator — AI Viết SQL
#### [NEW] `modules/sql/generator.py`
- Hàm `generate_sql(question, schema, rls_prompt, nlu_result)`: Trộn (System Prompt từ `prompts.yaml` + Schema + RLS + Few-shot SQL mẫu) → Gọi Groq Llama 3.3 70B → Trả về câu SQL thuần.
- Hàm `get_fewshot_examples(question)`: **Kỹ thuật RAG #6 (Auto-Tested Few-shot)** — Tìm 3 câu SQL mẫu tương tự nhất từ ChromaDB, đưa vào Prompt để AI bắt chước.
- Hàm `validate_fewshot_health()`: Chạy ngầm kiểm tra các câu SQL mẫu trên DB thật, xóa câu bị hỏng.

---

### 🔧 BƯỚC 5: SQL Validator — Cảnh sát Kiểm định SQL
#### [NEW] `modules/sql/validator.py`
- Hàm `validate_syntax(sql)`: Parse cú pháp SQL, bắt lỗi dư dấu `;`, dùng hàm không tồn tại.
- Hàm `enforce_security(sql, user)`: Gọi lại `validate_table_access()` (RBAC) và `validate_rls_sql()` (RLS) từ Giai đoạn 2.
- Hàm `enforce_query_limit(sql)`: **Query Limiter** — Kiểm tra nếu SQL là dạng `SELECT *` (dữ liệu thô) mà thiếu `LIMIT` → tự động dán `LIMIT 100` vào cuối câu.

---

### 🔧 BƯỚC 6: Self-Correction — AI Tự Sửa Lỗi
#### [NEW] `modules/sql/self_correction.py`
- Hàm `execute_with_retry(sql, max_retries=3)`:
  - Vòng lặp: Chạy SQL vào SQLite → Nếu lỗi → Gửi (SQL cũ + Traceback lỗi) cho AI viết lại → Chạy lại.
  - Tối đa 3 lần retry. Nếu vẫn lỗi → Trả thông báo lỗi thân thiện cho User.
- Đọc `correction_system_prompt` từ `prompts.yaml`.

---

### 🔧 BƯỚC 7: Tích hợp vào Máy chủ
#### [MODIFY] `main.py`
- Thay thế dòng giả lập `fake_sql_from_ai` bằng Pipeline thật:
  ```
  Câu hỏi → Guardrails → NLU → Schema Search → SQL Generator → SQL Validator → Self-Correction → Trả kết quả
  ```
- Kích hoạt Guardrails **Tầng 2 (AI Semantic)** hoạt động thật (vì `LLMProvider` đã sẵn sàng).

---

## 📋 DANH SÁCH FILE CẦN TẠO MỚI (TỔNG HỢP)

| # | File | Loại | Mục đích |
|---|---|---|---|
| 1 | `config/virtual_relationships.json` | [NEW] Config | Sơ đồ khóa ngoại ảo giữa các bảng |
| 2 | `config/synonyms.json` | [NEW] Config | Từ điển dịch từ lóng tiếng Việt |
| 3 | `modules/schema/engine.py` | [NEW] Python | Đọc Schema + Column Pruning + Data Profiling |
| 4 | `modules/schema/indexer.py` | [NEW] Python | ChromaDB Vector Search + Adaptive Rerank |
| 5 | `modules/nlu/engine.py` | [NEW] Python | Hiểu ngôn ngữ tự nhiên + Semantic Synonyms |
| 6 | `modules/sql/generator.py` | [NEW] Python | Sinh SQL bằng Groq Llama + Few-shot RAG |
| 7 | `modules/sql/validator.py` | [NEW] Python | Kiểm tra cú pháp + RBAC/RLS + Query Limiter |
| 8 | `modules/sql/self_correction.py` | [NEW] Python | Vòng lặp tự sửa lỗi SQL (max 3 retries) |
| 9 | `main.py` | [MODIFY] | Nối toàn bộ Pipeline thay thế `fake_sql_from_ai` |

---

## 🧪 KẾ HOẠCH KIỂM TRA (VERIFICATION PLAN)

### Test 1: Schema Engine
- Gọi `get_full_schema()` kiểm tra xem có đọc đúng 3 bảng (Sales, Customers, Products) + tất cả cột không.
- Gọi `prune_columns()` kiểm tra cột rác có bị cắt không.
- Gọi `profile_columns()` kiểm tra cột `Region` (< 50 values) có được nhét giá trị mẫu ("Miền Bắc", "Miền Nam") vào không.

### Test 2: NLU & Synonyms
- Đặt câu hỏi có từ lóng: *"Cho xem doanh số chốt đơn miền Bắc"* → Xem `preprocess_question()` có dịch thành *"Cho xem Revenue Completed_Orders miền Bắc"* không.

### Test 3: SQL Generator
- Đặt câu hỏi: *"Tổng doanh thu tháng 5"* → Xem AI có sinh ra `SELECT SUM(Revenue) FROM Sales WHERE ...` không.

### Test 4: Query Limiter
- Đặt câu hỏi mở: *"Cho xem toàn bộ đơn hàng"* → Xem SQL có tự động bị dán `LIMIT 100` không.

### Test 5: Self-Correction
- Cố tình cho AI sinh SQL sai (ví dụ: viết nhầm tên cột) → Xem AI có tự sửa lại đúng sau 1-2 lần retry không.

### Test 6: RBAC/RLS Integration
- Đăng nhập bằng `nam` (manager_north) → Đặt câu hỏi → Xem SQL sinh ra có bắt buộc chứa `WHERE Region='Miền Bắc'` không.

### Test 7: End-to-End
- Chạy toàn bộ Pipeline từ Swagger UI: Đăng nhập → Đặt câu hỏi → Nhận kết quả dữ liệu thật từ SQLite.

---

## 📌 GHI CHÚ BỔ SUNG

> [!NOTE]
> **Conversation Manager** (`modules/conversation/`) sẽ được triển khai ở **Giai đoạn 4**, SAU KHI Pipeline single-turn (1 câu hỏi → 1 câu trả lời) đã hoạt động ổn định.

> [!NOTE]
> **Kỹ thuật RAG #3 (Local Embedding Fallback)** đã được code sẵn ở `core/llm_providers.py` (Giai đoạn 1). Không cần code lại, chỉ cần gọi `get_fallback_embedding_model()` trong `indexer.py` khi Cohere lỗi.
