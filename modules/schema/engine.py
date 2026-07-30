import json
import os
import time
import yaml
from typing import List, Dict, Any, Optional

from core.logger import get_logger
from modules.data_source.base import DataConnector

logger = get_logger(__name__)

CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config")
SCHEMA_CONFIG_PATH = os.path.join(CONFIG_DIR, "schema_config.yaml")
VIRTUAL_REL_PATH = os.path.join(CONFIG_DIR, "virtual_relationships.json")

def _load_schema_config() -> dict:
    """Đọc file schema_config.yaml (danh sách cột rác + ngưỡng profiling)."""
    if os.path.exists(SCHEMA_CONFIG_PATH):
        with open(SCHEMA_CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}

def _load_virtual_relationships() -> dict:
    """Đọc file virtual_relationships.json (quan hệ dự phòng + nhóm cấm ghép)."""
    if os.path.exists(VIRTUAL_REL_PATH):
        with open(VIRTUAL_REL_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

class SchemaEngine:
    """
    Bộ não xử lý Schema. Phụ trách đọc cấu trúc Database, 
    cắt tỉa cột rác (RAG #1), tự suy diễn quan hệ (RAG #2) 
    và phân tích dữ liệu mẫu (RAG #5).
    
    ĐÃ VÁ 4 ĐIỂM YẾU:
    1. Luật Thép đọc exclude_groups từ JSON (không phụ thuộc tiền tố Fact_/Dim_).
    2. Column Pruning đọc danh sách rác từ schema_config.yaml (không hardcode).
    3. Data Profiling quét cả cột số có ít giá trị distinct.
    4. Caching trong RAM (chỉ quét lại khi hết TTL).
    """

    # Hàm khởi tạo __init__ của class SchemaEngine
    def __init__(self, connector: DataConnector, cache_ttl: int = 300):
        self.connector = connector
        self.cache_ttl = cache_ttl  # Thời gian sống của cache (giây), mặc định 5 phút
         
        # Cache storage
        self._cached_context: Optional[str] = None  # Lưu trữ context đã cache (kq đọc schema + quan hệ + profiling) -> nhét thẳng vào prompt cho AI
        self._cache_timestamp: float = 0  # Thời gian cache cuối cùng

    def prune_columns(self, schema: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Kỹ thuật RAG #1 (Column Pruning): Lọc bỏ các cột rác.
        [VÁ #2] Đọc danh sách rác từ schema_config.yaml thay vì hardcode.
        """
        config = _load_schema_config()
        trash_keywords = config.get("trash_column_keywords", [
            "password", "token", "hash", "created_at", "updated_at"
        ])
        
        pruned_schema = []
        for table in schema:
            pruned_columns = []
            for col in table["columns"]: # tạo ra một danh sách cột đã lọc theo dạng json: col = { "name": "CustomerTier",      # <-- Key "name" lưu TÊN của cột "type": "character varying"  # <-- Key "type" lưu KIỂU DỮ LIỆU của cột }
                col_lower = col["name"].lower() # name là tên cột
                is_trash = any(kw in col_lower for kw in trash_keywords)
                
                # Ngoại lệ: Giữ lại nếu nó là Khóa chính/Khóa ngoại
                is_key = "id" in col_lower or "key" in col_lower

                if not is_trash or is_key:
                    pruned_columns.append(col)
            
            if pruned_columns:
                table["columns"] = pruned_columns
                pruned_schema.append(table)
                
        logger.info(f"Column Pruning: Lọc xong, còn {sum(len(t['columns']) for t in pruned_schema)} cột hợp lệ.")
        return pruned_schema

    def detect_relationships(self) -> List[Dict[str, str]]:
        """
        Auto-Detect Gộp 3 Lớp.
        [VÁ #1] Đọc exclude_groups từ JSON thay vì chỉ dựa tiền tố Fact_/Dim_.
        """
        all_relationships = []
        seen_pairs = set()

        def add_relationship(from_t, from_c, to_t, to_c, source_layer):
            pair = tuple(sorted([f"{from_t}.{from_c}", f"{to_t}.{to_c}"]))
            if pair not in seen_pairs:
                seen_pairs.add(pair)
                all_relationships.append({
                    "from_table": from_t, "from_column": from_c,
                    "to_table": to_t, "to_column": to_c,
                    "source": source_layer
                })

        # --- LỚP 1: QUÉT FK VẬT LÝ TỪ DATABASE ---
        db_fks = self.connector.get_foreign_keys()
        for fk in db_fks:
            add_relationship(fk["from_table"], fk["from_column"], fk["to_table"], fk["to_column"], "DB_FK")

        # --- LỚP 2: NAMING CONVENTION (KÈM LUẬT THÉP) ---
        schema = self.connector.get_schema()
        VALID_SUFFIXES = ["id", "key", "code"]
        
        # [VÁ #1] Đọc exclude_groups từ JSON
        vr_config = _load_virtual_relationships()
        exclude_groups = vr_config.get("exclude_groups", [])
        
        # Tạo set các cặp bảng bị cấm ghép
        excluded_pairs = set()
        for group in exclude_groups:
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    excluded_pairs.add(tuple(sorted([group[i], group[j]])))
        
        id_columns_map = {}
        for table in schema:
            t_name = table["table_name"]
            for col in table["columns"]:
                c_name = col["name"]
                c_lower = c_name.lower()
                if any(suffix in c_lower for suffix in VALID_SUFFIXES):
                    if c_lower not in id_columns_map:
                        id_columns_map[c_lower] = []
                    id_columns_map[c_lower].append((t_name, c_name))
        
        for c_lower, occurrences in id_columns_map.items():
            if len(occurrences) > 1:
                for i in range(len(occurrences)):
                    for j in range(i + 1, len(occurrences)):
                        t1 = occurrences[i][0]
                        t2 = occurrences[j][0]
                        
                        # LUẬT THÉP: Kiểm tra cả tiền tố LẪN exclude_groups
                        t1_prefix = t1.split("_")[0].lower() if "_" in t1 else ""
                        t2_prefix = t2.split("_")[0].lower() if "_" in t2 else ""
                        if t1_prefix == t2_prefix and t1_prefix in ("fact", "dim"):
                            continue
                        
                        # [VÁ #1] Kiểm tra exclude_groups từ JSON
                        if tuple(sorted([t1, t2])) in excluded_pairs:
                            continue
                        
                        add_relationship(t1, occurrences[i][1], t2, occurrences[j][1], "NAMING_CONV")

        # --- LỚP 3: JSON FALLBACK ---
        for rel in vr_config.get("relationships", []):
            add_relationship(rel["from_table"], rel["from_column"], rel["to_table"], rel["to_column"], "JSON")

        logger.info(f"Auto-Detect Relations: Đã gộp thành công {len(all_relationships)} quan hệ.")
        return all_relationships

    def profile_columns(self, schema: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Kỹ thuật RAG #5 (Targeted Data Profiling).
        [VÁ #3] Quét cả cột số có ít giá trị distinct (< numeric_profiling_limit).
        """
        config = _load_schema_config()
        profiling_config = config.get("profiling", {})
        text_limit = profiling_config.get("text_profiling_limit", 50)
        numeric_limit = profiling_config.get("numeric_profiling_limit", 20)
        
        for table in schema:
            t_name = table["table_name"]
            for col in table["columns"]:
                c_name = col["name"]
                c_type = str(col["type"]).lower()
                
                # Xác định loại cột và ngưỡng tương ứng
                is_text = any(kw in c_type for kw in ["char", "text", "string", "object"])
                is_numeric = any(kw in c_type for kw in ["int", "numeric", "decimal", "float", "double", "smallint", "bigint"])
                is_boolean = "bool" in c_type
                
                # Bỏ qua boolean (chỉ có true/false, AI tự biết)
                if is_boolean:
                    continue
                
                if is_text:
                    samples = self.connector.get_sample_values(t_name, c_name, limit=text_limit)
                    if samples:
                        if len(samples) < text_limit:
                            col["sample_values"] = samples
                        else:
                            col["sample_values"] = ["(Quá đa dạng, AI hãy dùng ILIKE '%...%')"]
                            
                elif is_numeric:
                    # [VÁ #3] Quét cột số có ít giá trị distinct
                    samples = self.connector.get_sample_values(t_name, c_name, limit=numeric_limit)
                    if samples and len(samples) < numeric_limit:
                        col["sample_values"] = sorted(samples)

        logger.info("Hoàn tất Data Profiling.")
        return schema

    def format_schema_for_prompt(self, schema: List[Dict[str, Any]], relationships: List[Dict[str, str]]) -> str:
        """
        Gom (Schema + Quan hệ + Data Profiling) thành 1 chuỗi Text Markdown tối ưu.
        Đã thêm BẮT BUỘC dấu ngoặc kép (" ") cho bảng và cột để LLM dễ bắt chước cho PostgreSQL.
        """
        prompt = "## CẤU TRÚC DATABASE (Kèm Data Profiling):\n\n"
        for table in schema:
            prompt += f"### Bảng `\"{table['table_name']}\"`\n"
            for col in table["columns"]:
                col_str = f"- \"{col['name']}\" ({col['type']})"
                if "sample_values" in col:
                    col_str += f" | Mẫu: {col['sample_values']}"
                prompt += col_str + "\n"
            prompt += "\n"
            
        prompt += "## QUAN HỆ CÁC BẢNG (JOIN PATHS):\n\n"
        if not relationships:
            prompt += "Không tìm thấy quan hệ (AI tự suy luận hoặc báo lỗi).\n"
        else:
            for rel in relationships:
                prompt += f"- `\"{rel['from_table']}\".\"{rel['from_column']}\"` ➔ `\"{rel['to_table']}\".\"{rel['to_column']}\"` (Nguồn: {rel['source']})\n"

        return prompt

    def build_context(self, force_refresh: bool = False) -> str:
        """
        Hàm chính Pipeline.
        [VÁ #4] Có Caching trong RAM. Chỉ quét lại DB khi cache hết hạn.
        
        Args:
            force_refresh: Nếu True, bỏ qua cache và quét lại từ đầu.
        """
        now = time.time()
        
        # Kiểm tra cache còn sống không
        if not force_refresh and self._cached_context and (now - self._cache_timestamp) < self.cache_ttl:
            logger.info(f"Cache HIT! Trả về schema đã cache ({int(now - self._cache_timestamp)}s trước).")
            return self._cached_context
        
        logger.info("Cache MISS. Đang quét lại toàn bộ schema từ Database...")
        raw_schema = self.connector.get_schema()
        pruned_schema = self.prune_columns(raw_schema)
        profiled_schema = self.profile_columns(pruned_schema)
        relations = self.detect_relationships()
        
        result = self.format_schema_for_prompt(profiled_schema, relations)
        
        # Lưu vào cache
        self._cached_context = result
        self._cache_timestamp = now
        logger.info(f"Đã lưu cache schema (TTL: {self.cache_ttl}s).")
        
        return result