"""
NỘI DUNG CẦN LÀM:
- Khởi tạo FastAPI app
- CORS middleware (cho Streamlit gọi API)
- Startup event: Init ChromaDB, SQLite session DB, load security configs
- API Endpoints: /api/query, /api/auth/login, v.v.
"""
from fastapi import FastAPI, Depends
from contextlib import asynccontextmanager
import uvicorn
from core.logger import get_logger
from config.settings import settings
from config.database import init_databases

# IMPORT DÀN CẢNH SÁT BẢO MẬT VÀO MẶT TIỀN
from core.models import UserContext
from modules.security.auth import mock_login, get_current_user
from modules.security.rbac import validate_table_access
from modules.security.rls import generate_rls_prompt, validate_rls_sql
from modules.security.guardrails import validate_question_safety

logger = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("="*50)
    logger.info(f"🚀 KHỞI ĐỘNG MÁY CHỦ AI ANALYTICS (Môi trường: {settings.ENVIRONMENT})")
    logger.info("="*50)
    init_databases()
    yield  
    logger.info("🛑 Đã tắt máy chủ AI Analytics.")

app = FastAPI(
    title="AI Analytics Assistant API",
    description="Hệ thống trợ lý phân tích dữ liệu AI (Đã ráp Security Engine 🔒)",
    version="1.0.0",
    lifespan=lifespan
)

@app.get("/")
def health_check():
    return {"status": "success", "message": "Server đang chạy phà phà!"}

# =======================================================================
# 🎫 1. API ĐĂNG NHẬP (Lấy thẻ từ)
# =======================================================================
@app.get("/api/auth/login")
def login(username: str):
    """
    Hãy test thử bằng cách gõ 'admin' hoặc 'nam'. 
    Nó sẽ nhả ra 1 đoạn mã Token. Hãy copy đoạn mã đó dán vào Ổ Khóa 🔒 ở góc phải trên cùng!
    """
    token = mock_login(username)
    return {"access_token": token, "token_type": "bearer"}

# =======================================================================
# 🔒 2. API TRUY VẤN (Đã được Cảnh sát bảo vệ)
# =======================================================================
@app.post("/api/v1/query")
def process_query(question: str, current_user: UserContext = Depends(get_current_user)):
    """
    API này ĐÃ BỊ KHÓA. Nếu sếp không dán Token vào ổ khóa 🔒, Swagger sẽ báo lỗi 403 Forbidden!
    """
    # 0. Vành đai thép Lưới Lọc Kép kiểm duyệt câu hỏi (Tầng 1: Rule-based, Tầng 2: AI Semantic)
    is_safe, guard_msg = validate_question_safety(question)
    if not is_safe:
        return {
            "status": "THẤT BẠI ❌", 
            "error": f"Vành đai thép (Guardrails) đã chặn câu hỏi! Lý do: {guard_msg}"
        }

    # 1. RLS mớm luật vào Não AI
    rls_prompt = generate_rls_prompt(current_user)
    
    # 2. Giả lập con AI vừa sinh ra câu SQL này dựa trên câu hỏi của sếp
    fake_sql_from_ai = f"SELECT * FROM Sales WHERE Region='Miền Nam'" 
    
    # 3. Hai cảnh sát RBAC và RLS nhào vô xét duyệt câu SQL
    is_rbac_ok = validate_table_access(fake_sql_from_ai, current_user)
    is_rls_ok = validate_rls_sql(fake_sql_from_ai, current_user)
    
    if not is_rbac_ok or not is_rls_ok:
        return {
            "status": "THẤT BẠI ❌", 
            "error": "Cảnh sát Security đã chặn câu SQL này vì vi phạm quyền hạn của User!"
        }
        
    return {
        "status": "THÀNH CÔNG ✅",
        "user_login": f"{current_user.username} ({current_user.role})",
        "rls_prompt_sent_to_ai": rls_prompt,
        "fake_sql": fake_sql_from_ai
    }

if __name__ == "__main__":
    uvicorn.run("main:app", host="localhost", port=8000, reload=settings.DEBUG)
 