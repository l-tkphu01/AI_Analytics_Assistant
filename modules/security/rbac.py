"""
NỘI DUNG CẦN LÀM:
- Class RBACManager (check permissions, allowed tables từ roles.json)
""" 
from core.models import UserContext
from core.logger import get_logger

logger = get_logger(__name__)

def get_allowed_tables(user: UserContext) -> list:
    """Lấy danh sách Bảng được phép từ UserContext (đã nạp từ roles.json)."""
    if not user.attributes: # Thà giết lầm còn hơn bỏ sót
        return []
    
    # Rút trích đúng cái thuộc tính RBAC ra
    allowed = user.attributes.get("RBAC_Allowed_Tables", [])
    logger.debug(f"User {user.username} được quyền truy cập: {allowed}")
    return allowed

def validate_table_access(sql: str, user: UserContext) -> bool:
    """CẢNH SÁT KIỂM TRA BẢNG."""
    allowed_tables = get_allowed_tables(user)
    
    if "*" in allowed_tables:
        return True
        
    sql_upper = sql.upper()
    
    from modules.data_source.sqlite_source import SQLiteConnector
    connector = SQLiteConnector()
    schema = connector.get_schema() 
    all_tables_in_db = [t["table_name"].upper() for t in schema] # [SALES, CUSTOMERS, PRODUCTS...]
    
    for table in all_tables_in_db:
        if table in sql_upper and table not in [t.upper() for t in allowed_tables]:
            logger.error(f"❌ RBAC BÁO ĐỘNG: User cố tình truy cập bảng cấm: {table}")
            return False
            
    return True
