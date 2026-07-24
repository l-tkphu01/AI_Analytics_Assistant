# 🔍 BÁO CÁO KIỂM TRA TOÀN BỘ DỰ ÁN (CODE REVIEW)

Sau khi quét qua toàn bộ mã nguồn, tôi phân loại thành **3 mức độ nghiêm trọng**:

---

## 🔴 MỨC ĐỘ CAO (Cần sửa trước khi sang Bước 3)

### 1. `main.py` dòng 76: SQL HARDCODE giả lập
```python
fake_sql_from_ai = f"SELECT * FROM Sales WHERE Region='Miền Nam'"
```
- **Vấn đề:** API `/api/v1/query` hoàn toàn giả lập. Nó không gọi Schema Indexer, không gọi NLU, không sinh SQL thật. Đây là code placeholder từ giai đoạn thiết kế Security.
- **Khuyến nghị:** Đây là đúng theo thiết kế (chờ Bước 3+4 hoàn tất mới nối vào). Nhưng sếp cần **ghi nhớ** là sau khi xong NLU + SQL Generator, phải quay lại nối dây cho `main.py`.

### 2. `indexer.py` dòng 72-81: Đọc file YAML **MỖI LẦN** gọi hàm
```python
def _build_rich_description(self, ...):
    # Mở file YAML, parse YAML, đọc dict... LẶP LẠI 46 LẦN!
    config_path = os.path.join(...)
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
```
- **Vấn đề:** Hàm `_build_rich_description()` được gọi **46 lần** (1 lần cho mỗi cột). Mỗi lần nó mở file YAML, parse YAML, đọc dict. Lãng phí I/O ổ cứng!
- **Khuyến nghị:** Đọc YAML **1 lần duy nhất** trong `__init__()` hoặc `index_schema()`, lưu vào biến `self._column_descriptions`, rồi dùng lại.

---

## 🟡 MỨC ĐỘ TRUNG BÌNH (Nên sửa khi có thời gian)

### 3. `postgresql.py` dòng 70: SQL Injection tiềm ẩn
```python
cols_sql = f"""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_name = '{table_name}'
"""
```
- **Vấn đề:** Dùng f-string truyền thẳng `table_name` vào SQL mà không dùng **Parameterized Query**. Nếu tên bảng chứa ký tự đặc biệt (`'; DROP TABLE --`), lý thuyết có thể bị SQL Injection.
- **Khuyến nghị:** Dùng `cursor.execute(sql, (table_name,))` thay vì f-string. Tuy nhiên ở đây `table_name` đến từ `information_schema` (do DB tự sinh) nên rủi ro thực tế **rất thấp**.

### 4. `postgresql.py` dòng 42, 61, 73: Warning `pandas` liên tục
```
UserWarning: pandas only supports SQLAlchemy connectable...
```
- **Vấn đề:** Mỗi lần chạy đều hiện cảnh báo vàng vì sếp đang dùng `psycopg2` thuần thay vì `SQLAlchemy engine`.
- **Khuyến nghị:** Thêm 1 dòng `import warnings; warnings.filterwarnings("ignore", category=UserWarning)` hoặc nâng cấp lên dùng `sqlalchemy.create_engine(DATABASE_URL)`.

### 5. `indexer.py` hàm `get_relevant_schema_for_prompt()`: Gọi lại DB 3 lần
```python
raw_schema = self.connector.get_schema()      # Gọi DB lần 1
pruned_schema = self.engine.prune_columns(...)
profiled_schema = self.engine.profile_columns(...)  # Gọi DB lần 2 (get_sample_values)
all_relations = self.engine.detect_relationships()  # Gọi DB lần 3 (get_foreign_keys)
```
- **Vấn đề:** Mỗi lần user hỏi câu hỏi, hàm này gọi lại DB 3 lần. Trong khi `SchemaEngine` đã có cơ chế `build_context()` với Cache TTL 5 phút.
- **Khuyến nghị:** Nên cache kết quả `profiled_schema` và `all_relations` để các lần gọi tiếp theo không phải quét lại DB.

---

## 🟢 MỨC ĐỘ THẤP (Ghi nhận, không cần sửa ngay)

### 6. File rác nằm ngoài thư mục
Các file `.md` nằm lung tung ở thư mục gốc:
- `implementation_plan.md`, `implementation_plan01`
- `conversation_manager_architecture.md`
- `local_cache_architecture.md`, `rag_engine_architecture.md`
- `security_architecture.md`, `security_engine_roadmap.md`
- **Khuyến nghị:** Dọn vào thư mục `docs/`.

### 7. `requirements.txt` thiếu pinning version
```
fastapi        # Nên là: fastapi==0.115.0
chromadb       # Nên là: chromadb==0.5.0
```
- **Vấn đề:** Không ghim version. Ngày mai `chromadb` ra bản mới có breaking change, code sẽ vỡ.
- **Khuyến nghị:** Chạy `pip freeze > requirements.txt` để ghim version chính xác.

### 8. `settings.py` dòng 27: JWT Secret Key mặc định
```python
JWT_SECRET_KEY: str = "default_secret_key"
```
- **Vấn đề:** Giá trị mặc định quá yếu. Nếu quên đổi trong `.env` khi deploy lên Production, bất kỳ ai cũng có thể giả mạo Token.
- **Khuyến nghị:** Đây là môi trường Dev nên chấp nhận được. Nhưng cần ghi TODO nhắc nhở trước khi deploy.

---

## 📊 TỔNG KẾT

| Mức độ | Số lượng | Hành động |
|--------|----------|-----------|
| 🔴 Cao | 2 | Sửa ngay item #2 (YAML đọc lặp). Item #1 chờ Bước 3+4 |
| 🟡 Trung bình | 3 | Sửa khi refactor |
| 🟢 Thấp | 3 | Ghi nhận, không cần sửa ngay |

> [!IMPORTANT]
> Sếp muốn tôi **vá ngay Item #2** (fix YAML đọc lặp 46 lần) trước khi sang Bước 3 không? Chỉ mất 2 phút thôi!
