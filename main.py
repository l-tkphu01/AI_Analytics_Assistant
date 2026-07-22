"""
NỘI DUNG CẦN LÀM:
- Khởi tạo FastAPI app
- CORS middleware (cho Streamlit gọi API)
- Startup event: Init ChromaDB, SQLite session DB, load security configs
- API Endpoints: /api/query, /api/export/pdf, /api/export/docx, /api/schema/tables, /api/schema/index, /api/health, /api/auth/login, /api/history
- Dependency Injection: get_current_user(), get_data_connector()
"""
from fastapi import FastAPI
from contextlib import asynccontextmanager
import uvicorn
from core.logger import get_logger
from config.settings import settings
from config.database import init_databases

logger = get_logger(__name__)

# Thay thế on_event bằng lifespan (Chuẩn FastAPI hiện đại)
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Phần này chạy khi Server vừa BẬT lên
    logger.info("="*50)
    logger.info(f"🚀 KHỞI ĐỘNG MÁY CHỦ AI ANALYTICS (Môi trường: {settings.ENVIRONMENT})")
    logger.info("="*50)
    init_databases()
    
    yield  # Giao lại quyền điều khiển cho Server chạy
    
    # Phần này chạy khi Server TẮT (Bấm Ctrl+C)
    logger.info("🛑 Đã tắt máy chủ AI Analytics.")

# Khởi tạo Rạp hát FastAPI
app = FastAPI(
    title="AI Analytics Assistant API",
    description="Hệ thống trợ lý phân tích dữ liệu AI (Zero-Cost)",
    version="1.0.0",
    lifespan=lifespan  # Gắn cái vòng đời ở trên vào đây
)

@app.get("/")
def health_check():
    """API kiểm tra xem Server còn sống hay đã ngủm"""
    return {
        "status": "success", 
        "message": "AI Analytics Server đang chạy phà phà!",
        "environment": settings.ENVIRONMENT
    }

@app.post("/api/v1/query")
def process_query(question: str):
    """
    (TẠM THỜI CHỜ XÂY DỰNG)
    Đây sẽ là Cái mồm của hệ thống. 
    """
    return {"message": f"Sếp vừa hỏi: '{question}'. Hệ thống NLU và SQL đang được xây, ráng đợi chút!"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=settings.DEBUG)
