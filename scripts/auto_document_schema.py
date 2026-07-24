import os
import sys
import json
import yaml

# Thêm root_dir vào sys.path để import được các module từ thư mục cha
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
if root_dir not in sys.path:
    sys.path.append(root_dir)

from dotenv import load_dotenv
load_dotenv()

from core.logger import get_logger
from config.settings import settings
from modules.data_source.base import get_connector
from modules.schema.engine import SchemaEngine
from core.llm_providers import LLMProvider

logger = get_logger(__name__)

# Bảng màu cho Terminal
class C:
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    RESET = '\033[0m'

# Đảm bảo UTF-8
if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def generate_schema_documentation():
    print(f"\n{C.CYAN}{C.BOLD}🚀 KHỞI ĐỘNG HỆ THỐNG LLM AUTO-DOCUMENTER{C.RESET}")
    print(f"{C.CYAN}{'='*80}{C.RESET}")

    # 1. Khởi tạo kết nối DB và Schema Engine
    connector = get_connector(settings.DATA_SOURCE)
    if not connector.test_connection():
        logger.error(f"{C.RED}❌ Lỗi kết nối Database!{C.RESET}")
        return

    engine = SchemaEngine(connector)
    print(f"{C.YELLOW}⏳ Đang đọc và dọn dẹp cấu trúc Database (Schema Profiling)...{C.RESET}")
    raw_schema = connector.get_schema()
    pruned_schema = engine.prune_columns(raw_schema)
    profiled_schema = engine.profile_columns(pruned_schema)
    
    # 2. Chuẩn bị prompt cho LLM
    print(f"{C.YELLOW}⏳ Khởi tạo AI (Gemini/Llama 3)...{C.RESET}")
    llm = LLMProvider.get_sql_llm() # Sử dụng LLM chính

    # Gom nhóm thông tin các cột thành chuỗi để LLM đọc
    # [VÁ LỖ HỔNG #2] Tự động phát hiện cột Key/ID kỹ thuật và đánh dấu riêng
    schema_text = ""
    table_names = []
    for table in profiled_schema:
        t_name = table['table_name']
        table_names.append(t_name)
        schema_text += f"\n--- Bảng: {t_name} ---\n"
        for col in table["columns"]:
            samples = col.get("sample_values", [])
            c_name = col['name']
            c_lower = c_name.lower()
            
            # Đánh dấu cột Key/ID để LLM biết đây là cột kỹ thuật
            is_key = c_lower.endswith("key") or c_lower.endswith("id")
            key_tag = " [CỘT KHÓA KỸ THUẬT - BỎ QUA]" if is_key else ""
            
            schema_text += f"- Cột: {c_name} | Kiểu: {col['type']} | Mẫu: {samples}{key_tag}\n"

    # [VÁ LỖ HỔNG #1] Tự suy luận Domain Context từ tên bảng
    domain_hint = ", ".join(table_names)

    prompt = f"""Bạn là một Chuyên gia Dữ liệu (Data Engineer / Data Steward) lão luyện.

## NGỮ CẢNH NGÀNH (DOMAIN CONTEXT):
Database này chứa các bảng: [{domain_hint}].
Hãy dựa vào tên các bảng trên để suy luận đây là hệ thống thuộc ngành nghề gì (Bán lẻ, Y tế, Logistics, Nhân sự...), rồi dịch các cột cho phù hợp với ngữ cảnh ngành đó.

## NHIỆM VỤ:
Suy luận và viết ra **Ý NGHĨA NGHIỆP VỤ** cho từng cột. Tuân thủ các quy tắc sau:

### QUY TẮC BẮT BUỘC:
1. **BỎ QUA** hoàn toàn các cột có gắn tag [CỘT KHÓA KỸ THUẬT - BỎ QUA]. Không đưa chúng vào JSON kết quả.
2. Mỗi cột phải có **ít nhất 3-5 từ/cụm từ đồng nghĩa**, cách nhau bằng dấu phẩy.
3. **BẮT BUỘC** viết cả tiếng Việt LẪN tiếng Anh để Vector Search bắt được cả hai ngôn ngữ.
4. Ưu tiên viết theo cách người dùng bình thường hay gọi trong đời sống (ví dụ: "doanh thu" thay vì "tổng giá trị giao dịch ròng").

### VÍ DỤ MẪU:
- 'SalesAmount' → 'doanh thu, doanh số bán hàng, tổng tiền bán, revenue, total sales'
- 'stockonhand' → 'tồn kho, hàng tồn, số lượng còn trong kho, stock, inventory on hand'
- 'patient_bp' → 'huyết áp bệnh nhân, blood pressure, chỉ số huyết áp'
- 'Region' (ngành Bán lẻ) → 'vùng miền, khu vực bán hàng, miền bắc miền nam miền trung, sales region'

## ĐỊNH DẠNG OUTPUT:
BẮT BUỘC CHỈ TRẢ VỀ JSON HỢP LỆ (Không chứa markdown, không giải thích gì thêm):
{{
    "tên_cột_chữ_thường": "từ_khóa_tiếng_việt, từ_khóa_tiếng_anh, ...",
    "salesamount": "doanh thu, doanh số, revenue, total sales"
}}

## DỮ LIỆU CẦN PHÂN TÍCH:
{schema_text}
"""
    
    print(f"{C.YELLOW}🤖 Đang ném dữ liệu cho LLM dự đoán ý nghĩa... (Chờ khoảng 5-10 giây){C.RESET}")
    try:
        response = llm.invoke(prompt)
        content = response.content.strip()
        
        # Tiền xử lý để loại bỏ markdown nếu LLM cứng đầu vẫn trả về
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        
        content = content.strip()
        
        # Parse JSON
        new_descriptions = json.loads(content)
        print(f"{C.GREEN}✅ LLM đã phân tích thành công {len(new_descriptions)} cột!{C.RESET}")
        
    except Exception as e:
        logger.error(f"{C.RED}❌ Lỗi gọi LLM hoặc Parse JSON: {e}\n{response.content if 'response' in locals() else ''}{C.RESET}")
        return

    # 3. Ghi đè vào config/schema_config.yaml
    config_path = os.path.join(root_dir, "config", "schema_config.yaml")
    
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config_data = yaml.safe_load(f) or {}
    except FileNotFoundError:
        config_data = {}

    # Cập nhật dict
    if "column_descriptions" not in config_data:
        config_data["column_descriptions"] = {}
        
    config_data["column_descriptions"].update(new_descriptions)

    # Ghi lại file YAML
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(config_data, f, allow_unicode=True, sort_keys=False)
        
    print(f"{C.GREEN}{C.BOLD}🎉 TUYỆT VỜI! Đã tự động ghi {len(new_descriptions)} mô tả vào file config/schema_config.yaml.{C.RESET}")
    print(f"{C.CYAN}Sếp có thể mở file YAML lên kiểm tra và chỉnh sửa thủ công nếu LLM đoán sai 1-2 cột. Sau đó hãy chạy lại `index_schema()` để nạp vào ChromaDB nhé!{C.RESET}\n")

if __name__ == "__main__":
    generate_schema_documentation()
