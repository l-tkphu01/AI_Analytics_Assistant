"""
NỘI DUNG CẦN LÀM:
- JWT authentication (create_token, verify_token, hash_password)
"""
import jwt
from datetime import datetime, timedelta
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from core.models import UserContext
from config.settings import settings
from core.logger import get_logger

logger = get_logger(__name__)

# Khai báo cơ chế bảo mật Bearer Token của FastAPI
security_scheme = HTTPBearer()

def create_access_token(user_id: str, username: str, role: str, attributes: dict = None) -> str:
    """Tạo JWT Token chứa thông tin phân quyền của người dùng."""
    expire = datetime.utcnow() + timedelta(hours=24) # Thẻ từ có giá trị 24 tiếng
    
    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
        "attributes": attributes or {},
        "exp": expire
    }
    
    # Ký đóng dấu bằng chìa khóa bí mật (lấy từ settings.py)
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    logger.info(f"Đã cấp Token cho User: {username} (Role: {role})")
    return token

def verify_token(token: str) -> UserContext:
    """Giải mã Thẻ từ (Token) và dựng lại bản sao quyền hạn của User."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        
        return UserContext(
            user_id=payload.get("sub"),
            username=payload.get("username"),
            role=payload.get("role"),
            attributes=payload.get("attributes", {})
        )
    except jwt.ExpiredSignatureError:
        logger.warning("Truy cập từ chối: Token đã hết hạn!")
        raise HTTPException(status_code=401, detail="Token đã hết hạn. Vui lòng đăng nhập lại.")
    except jwt.InvalidTokenError:
        logger.error("BÁO ĐỘNG: Phát hiện Token giả mạo!")
        raise HTTPException(status_code=401, detail="Token không hợp lệ hoặc đã bị chỉnh sửa.")

def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security_scheme)) -> UserContext:
    """
    CẢNH SÁT GÁC CỔNG FASTAPI. 
    Bất kỳ Endpoint nào muốn bảo mật, chỉ cần gắn Dependency này vào.
    """
    token = credentials.credentials
    return verify_token(token)

# =====================================================================
# 🔥 TÍNH NĂNG ĐĂNG NHẬP GIẢ LẬP (MOCK LOGIN) DÀNH CHO QUÁ TRÌNH TEST
# =====================================================================
def mock_login(username: str) -> str:
    """Hàm tạo Token giả lập nhanh chóng để test API mà không cần Database thật."""
    if username.lower() == "admin":
        # Giám đốc: Không bị dính giới hạn vùng miền (RLS)
        return create_access_token("u1", "Sếp Tổng", "admin", {})
    elif username.lower() == "nam":
        # Nhân viên Nam: Chỉ được xem data Miền Bắc (RLS)
        return create_access_token("u2", "Trần Văn Nam", "staff", {"region": "Miền Bắc"})
    else:
        # Mặc định nhân viên quèn: Chỉ được xem Miền Nam
        return create_access_token("u3", "Nhân viên Vô danh", "staff", {"region": "Miền Nam"})
