"""
NỘI DUNG CẦN LÀM:
- JWT authentication (create_token, verify_token, hash_password)
"""
import jwt 
import yaml
import os 
from datetime import datetime, timedelta
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from core.models import UserContext
from config.settings import settings
from core.logger import get_logger

logger = get_logger(__name__)

security_scheme = HTTPBearer()

def get_role_attributes(role_name: str) -> dict:
    """Đọc file roles.yaml để lấy luật RLS + RBAC tương ứng với Role."""
    roles_path = os.path.join(os.path.dirname(__file__), "..", "..", "config", "roles.yaml")
    try: 
        with open(roles_path, "r", encoding="utf-8") as f:
            roles_data = yaml.safe_load(f) 
            return roles_data.get(role_name, {})
    except Exception as e:
        logger.error(f"Không thể đọc file roles.yaml: {e}")
        return {}

def create_access_token(user_id: str, username: str, role: str) -> str:
    """Tạo JWT Token (Chỉ chứa ID và Chức vụ, KHÔNG chứa attributes)."""
    expire = datetime.utcnow() + timedelta(hours=24)
    
    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
        "exp": expire
    }
    
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    logger.info(f"Đã cấp Token cho User: {username} (Role: {role})")
    return token

def verify_token(token: str) -> UserContext:
    """Giải mã Token và tự động chui vào roles.json để lấy quyền RLS."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        role = payload.get("role")
        
        # BƯỚC 3: Tra cứu RLS Context từ roles.json
        rls_attributes = get_role_attributes(role)
        
        return UserContext(
            user_id=payload.get("sub"),
            username=payload.get("username"),
            role=role,
            attributes=rls_attributes # Lấy thông tin RLS từ file roles.yaml
        )
    except jwt.ExpiredSignatureError:
        logger.warning("Truy cập từ chối: Token đã hết hạn!")
        raise HTTPException(status_code=401, detail="Token đã hết hạn. Vui lòng đăng nhập lại.")
    except jwt.InvalidTokenError:
        logger.error("BÁO ĐỘNG: Phát hiện Token giả mạo!")
        raise HTTPException(status_code=401, detail="Token không hợp lệ.")

def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security_scheme)) -> UserContext:
    """CẢNH SÁT GÁC CỔNG FASTAPI."""
    token = credentials.credentials
    return verify_token(token)

def mock_login(username: str) -> str:
    """Hàm tạo Token giả lập (Truyền đúng tên Role trong roles.json)."""
    if username.lower() == "admin":
        return create_access_token("u1", "Sếp Tổng", "admin")
    elif username.lower() == "nam":
        return create_access_token("u2", "Trần Văn Nam", "manager_north")
    else:
        return create_access_token("u3", "Nhân viên Vô danh", "manager_south")
