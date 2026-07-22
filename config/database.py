import sqlite3
import os
from core.logger import get_logger
from config.settings import settings

logger = get_logger(__name__)

# Đường dẫn mặc định cho các SQLite database nội bộ
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
SESSIONS_DB_PATH = os.path.join(DATA_DIR, "sessions.db")
AUDIT_DB_PATH = os.path.join(DATA_DIR, "audit.db")

def get_session_db() -> sqlite3.Connection:
    """Trả về kết nối tới SQLite lưu lịch sử chat (Conversation Memory)."""
    os.makedirs(DATA_DIR, exist_ok=True)
    # Check_same_thread=False để chống lỗi FastAPI đa luồng
    conn = sqlite3.connect(SESSIONS_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row  
    return conn

def get_audit_db() -> sqlite3.Connection:
    """Trả về kết nối tới SQLite lưu lịch sử truy vấn (Audit Trail)."""
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(AUDIT_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

# Check Mock_data
def get_business_db() -> sqlite3.Connection:
    """
    Vá lỗi 3: Trả về kết nối tới Database Kinh Doanh thật sự.
    Tạm thời dùng SQLite giả lập. Sau này sẽ if/else để nối vào Fabric/Postgres.
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    MOCK_BUSINESS_DB = os.path.join(DATA_DIR, "business_mock.db")
    conn = sqlite3.connect(MOCK_BUSINESS_DB, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_databases():
    """Tạo toàn bộ tables cần thiết nếu chưa tồn tại."""
    
    # 1. Bảng Sessions
    session_conn = get_session_db()
    session_conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            memory_json TEXT DEFAULT '[]',
            last_query TEXT,
            last_sql TEXT,
            last_dataframe_hash TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    session_conn.commit()
    session_conn.close()
    logger.info(f"Sessions DB đã sẵn sàng: {SESSIONS_DB_PATH}")

    # 2. Bảng Audit Logs
    audit_conn = get_audit_db()
    audit_conn.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            query_text TEXT NOT NULL,
            generated_sql TEXT,
            row_count INTEGER DEFAULT 0,
            execution_time_ms REAL DEFAULT 0,
            status TEXT DEFAULT 'success',
            data_source TEXT,
            error_message TEXT,
            used_tables TEXT,       -- Vá lỗi 2: Thêm cột hứng danh sách bảng
            token_metadata TEXT,    -- Vá lỗi 2: Thêm cột hứng số Token/Tiền API
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    audit_conn.commit()
    audit_conn.close()
    logger.info(f"Audit DB đã sẵn sàng: {AUDIT_DB_PATH}")

    logger.info("Khởi tạo databases hoàn tất!")
