"""
SQL VALIDATOR — Cảnh sát Kiểm định SQL (Bước 4B)

Kiểm tra SQL do AI sinh ra TRƯỚC KHI chạy vào Database:
1. validate_syntax()     → Chặn lệnh nguy hiểm (INSERT, DELETE, DROP)
2. enforce_security()    → Gọi RBAC + RLS kiểm tra quyền hạn
3. enforce_query_limit() → Tự dán LIMIT 100 nếu SQL thiếu LIMIT
4. validate()            → Hàm tổng: Chạy cả 3 bước trên
"""
import re
from typing import Dict, Any, Optional
from core.logger import get_logger

logger = get_logger(__name__)

# Danh sách từ khóa SQL nguy hiểm (Chỉ cho phép SELECT)
DANGEROUS_KEYWORDS = [
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE",
    "TRUNCATE", "EXEC", "EXECUTE", "GRANT", "REVOKE",
    "MERGE", "REPLACE INTO"
]


class SQLValidator:
    """
    Cảnh sát kiểm tra SQL: Cú pháp + Bảo mật + Query Limit.
    Không cần AI, hoàn toàn Rule-based (nhanh, chính xác, miễn phí).
    """

    def __init__(self, connector=None):
        self.connector = connector

    def validate_syntax(self, sql: str) -> Dict[str, Any]:
        """
        Kiểm tra cú pháp SQL cơ bản:
        - Chặn lệnh nguy hiểm (INSERT, DELETE, DROP...)
        - Chặn nhiều câu SQL ghép (SQL Injection qua ;)
        - Kiểm tra SQL không rỗng
        
        Returns:
            {"valid": True/False, "error": "Lý do" hoặc None}
        """
        if not sql or not sql.strip():
            return {"valid": False, "error": "Câu SQL rỗng."}

        sql_clean = sql.strip()
        sql_upper = sql_clean.upper()

        # 1. Chặn lệnh nguy hiểm
        for keyword in DANGEROUS_KEYWORDS:
            # Dùng word boundary (\b) để tránh match nhầm (vd: "SELECTED" ≠ "DELETE")
            pattern = r'\b' + keyword.replace(' ', r'\s+') + r'\b'
            if re.search(pattern, sql_upper):
                logger.error(f"❌ SQL Validator: Phát hiện lệnh nguy hiểm '{keyword}'!")
                return {
                    "valid": False,
                    "error": f"Câu SQL chứa lệnh nguy hiểm: {keyword}. Chỉ được dùng SELECT."
                }

        # 2. Kiểm tra phải bắt đầu bằng SELECT hoặc WITH (CTE)
        if not sql_upper.lstrip().startswith(("SELECT", "WITH")):
            logger.error(f"❌ SQL Validator: SQL không bắt đầu bằng SELECT hoặc WITH!")
            return {
                "valid": False,
                "error": "Câu SQL phải bắt đầu bằng SELECT (hoặc WITH cho CTE)."
            }

        # 3. Chặn nhiều câu SQL ghép bằng dấu ; (phòng SQL Injection)
        # Loại bỏ dấu ; ở cuối (hợp lệ), chỉ chặn ; ở giữa
        sql_no_trailing = sql_clean.rstrip(";").strip()
        
        # MẸO: Xóa "ảo" tất cả nội dung nằm trong nháy đơn ('...') và nháy kép ("...") 
        # để tránh bắt oan dấu ; nằm trong dữ liệu text.
        sql_safe_check = re.sub(r"'(?:''|[^'])*'", "''", sql_no_trailing)
        sql_safe_check = re.sub(r'"(?:""|[^"])*"', '""', sql_safe_check)

        if ";" in sql_safe_check:
            logger.error(f"❌ SQL Validator: Phát hiện nhiều câu SQL ghép (dấu ; ở giữa)!")
            return {
                "valid": False,
                "error": "Không được ghép nhiều câu SQL. Chỉ được 1 câu SELECT duy nhất."
            }

        logger.info("✅ SQL Validator: Cú pháp hợp lệ.")
        return {"valid": True, "error": None}

    def enforce_security(self, sql: str, user=None) -> Dict[str, Any]:
        """
        Kiểm tra bảo mật: RBAC (quyền xem bảng) + RLS (lọc dòng).
        Gọi lại hàm từ Security Engine đã xây ở Bước 1.
        
        Returns:
            {"valid": True/False, "error": "Lý do" hoặc None}
        """
        if user is None:
            # Không có thông tin user → Bỏ qua kiểm tra bảo mật
            logger.info("SQL Validator: Không có user context, bỏ qua kiểm tra bảo mật.")
            return {"valid": True, "error": None}

        try:
            # Kiểm tra RBAC (user có quyền xem bảng đó không?)
            from modules.security.rbac import validate_table_access
            if not validate_table_access(sql, user):
                return {
                    "valid": False,
                    "error": f"User '{user.username}' không có quyền truy cập bảng trong câu SQL này."
                }

            # Kiểm tra RLS (câu SQL có chứa điều kiện WHERE bắt buộc không?)
            from modules.security.rls import validate_rls_sql
            if not validate_rls_sql(sql, user):
                return {
                    "valid": False,
                    "error": f"Câu SQL thiếu điều kiện bảo mật (RLS) bắt buộc cho user '{user.username}'."
                }

            logger.info("✅ SQL Validator: Bảo mật hợp lệ (RBAC + RLS).")
            return {"valid": True, "error": None}

        except Exception as e:
            logger.error(f"SQL Validator: Lỗi kiểm tra bảo mật: {e}")
            return {"valid": False, "error": f"Lỗi kiểm tra bảo mật: {str(e)}"}

    def enforce_query_limit(self, sql: str, default_limit: int = 100) -> str:
        """
        Query Limiter: Nếu SQL thiếu LIMIT → Tự động thêm LIMIT 100.
        Tránh user vô tình SELECT * ra hàng triệu dòng làm sập DB.
        
        Returns:
            Câu SQL đã được gắn LIMIT (nếu cần).
        """
        sql_upper = sql.upper().strip()

        # Nếu SQL đã có LIMIT → Giữ nguyên
        if "LIMIT" in sql_upper:
            logger.debug("SQL Validator: SQL đã có LIMIT, giữ nguyên.")
            return sql

        # Nếu SQL là dạng tổng hợp (SUM, COUNT, AVG...) → Không cần LIMIT
        agg_functions = ["SUM(", "COUNT(", "AVG(", "MIN(", "MAX("]
        has_agg = any(func in sql_upper for func in agg_functions)
        has_group_by = "GROUP BY" in sql_upper

        if has_agg and not has_group_by:
            # SQL chỉ trả về 1 dòng (ví dụ: SELECT SUM(...)) → Không cần LIMIT
            logger.debug("SQL Validator: SQL tổng hợp (1 dòng), không cần LIMIT.")
            return sql

        # Các trường hợp còn lại → Dán LIMIT
        sql_with_limit = f"{sql.rstrip()}\nLIMIT {default_limit}"
        logger.info(f"SQL Validator: Đã tự động thêm LIMIT {default_limit}.")
        return sql_with_limit

    def _fix_postgres_quotes(self, sql: str) -> str:
        """
        Bọc ngoặc kép (" ") cho các tên bảng phổ biến nếu AI quên.
        PostgreSQL phân biệt hoa/thường, nếu không bọc ngoặc, nó sẽ tìm "fact_sales" thay vì "Fact_Sales".
        """
        # Lấy danh sách bảng động từ Database (Không hardcode!)
        tables = []
        if self.connector:
            try:
                schema = self.connector.get_schema()
                tables = [t["table_name"] for t in schema]
            except Exception as e:
                logger.warning(f"SQL Validator: Không thể lấy danh sách bảng động: {e}")
        
        fixed_sql = sql
        for table in tables:
            # Tìm table name không có ngoặc kép (trước và sau nó là khoảng trắng hoặc dấu chấm)
            # (?<!")Table(?!")
            pattern = r'(?<!")\b' + table + r'\b(?!")'
            fixed_sql = re.sub(pattern, f'"{table}"', fixed_sql, flags=re.IGNORECASE)
            
        return fixed_sql

    def validate(self, sql: str, user=None) -> Dict[str, Any]:
        """
        Hàm tổng: Chạy cả 3 bước kiểm tra.
        
        Returns:
            {
                "valid": True/False,
                "sql": "Câu SQL đã qua xử lý (có thể đã thêm LIMIT)",
                "error": "Lý do từ chối" hoặc None
            }
        """
        # Bước 1: Kiểm tra cú pháp
        syntax_result = self.validate_syntax(sql)
        if not syntax_result["valid"]:
            return {"valid": False, "sql": sql, "error": syntax_result["error"]}

        # Bước 2: Kiểm tra bảo mật (RBAC + RLS)
        security_result = self.enforce_security(sql, user)
        if not security_result["valid"]:
            return {"valid": False, "sql": sql, "error": security_result["error"]}

        # Bước 3: Tự động thêm LIMIT nếu thiếu
        safe_sql = self.enforce_query_limit(sql)

        # Bước 4: Vá lỗi ngoặc kép cho PostgreSQL (Force Fix)
        safe_sql = self._fix_postgres_quotes(safe_sql)

        logger.info("✅ SQL Validator: Tất cả kiểm tra PASSED.")
        return {"valid": True, "sql": safe_sql, "error": None}