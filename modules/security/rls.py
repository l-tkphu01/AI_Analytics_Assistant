"""
NỘI DUNG CẦN LÀM:
- Class RLSManager (inject WHERE clause từ rls_config.json)
"""
from core.models import UserContext
from core.logger import get_logger

logger = get_logger(__name__)
 
def generate_rls_prompt(user: UserContext) -> str:
    """Sinh ra Prompt ép buộc con AI phải áp dụng RLS."""
    if not user.attributes:
        return ""  # Nếu không có thuộc tính gì thì cho qua (Admin)
     
    rules = [] 
    for key, value in user.attributes.items():
        # LỌC RÁC: Chỉ lấy những thuộc tính có chữ RLS_ ở đầu (bỏ qua RBAC_Allowed_Tables)
        if key.startswith("RLS_") and value:
            clean_key = key.replace("RLS_", "") # Cắt chữ RLS_ đi, chỉ chừa lại chữ 'Region'
            rules.append(f"Cột '{clean_key}' PHẢI LUÔN LÀ '{value}'")
            
    # Nếu User này chỉ có quyền RBAC mà không có luật RLS nào thì khỏi sinh Prompt
    if not rules:
        return ""
        
    prompt = "\n--- CẢNH BÁO BẢO MẬT (ROW-LEVEL SECURITY) ---\n"
    prompt += "Bạn BẮT BUỘC phải thêm điều kiện WHERE vào câu SQL với các quy tắc sau:\n- "
    prompt += "\n- ".join(rules)
    prompt += "\nNếu bạn bỏ qua điều kiện này, hệ thống sẽ từ chối thực thi câu SQL!"
    
    logger.debug(f"Đã sinh RLS Prompt cho User {user.user_id}")
    return prompt

def validate_rls_sql(sql: str, user: UserContext) -> bool:
    """
    CẢNH SÁT KIỂM TRA DÒNG (RLS).
    Kiểm tra câu SQL do AI tạo ra xem có chứa điều kiện WHERE bắt buộc không.
    """
    if not user.attributes:
        return True
        
    sql_upper = sql.upper()
    for key, value in user.attributes.items():
        if key.startswith("RLS_") and value:
            # Kiểm tra xem cái giá trị (ví dụ: MIỀN BẮC) có nằm trong câu SQL không
            if str(value).upper() not in sql_upper:
                logger.warning(f"❌ RLS BÁO ĐỘNG: Câu SQL bị từ chối vì thiếu điều kiện bảo mật cho {key}='{value}'")
                return False
            
    logger.info(f"✅ RLS Hợp lệ cho User {user.user_id}")
    return True
