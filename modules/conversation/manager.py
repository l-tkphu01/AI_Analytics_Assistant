import sqlite3
import json
from typing import List, Dict
from core.logger import get_logger

logger = get_logger(__name__)

class ConversationManager:
    """
    Quản lý lịch sử hội thoại dựa trên kiến trúc JSON Gom Cụm (Document-oriented).
    Toàn bộ phiên chat được lưu vào 1 mảng JSON trong duy nhất 1 ô database.
    """
    def __init__(self, db_path: str = "data/sessions.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Khởi tạo bảng sessions"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS sessions (
                        session_id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        memory_json TEXT NOT NULL,
                        last_query TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                # Index hỗ trợ tìm kiếm tất cả session của 1 user (cho tính năng Sidebar sau này)
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_id ON sessions (user_id)')
                conn.commit()
                logger.info(f"✅ Đã khởi tạo bảng sessions trong {self.db_path}")
        except Exception as e:
            logger.error(f"⚠️ Lỗi khởi tạo bảng sessions: {e}")

    def add_turn(self, session_id: str, user_id: str, user_msg: str, ai_msg: str, chart_json: str = None, data: list = None, sql: str = None, chart_config: dict = None, narrative: str = None):
        """
        Ghi đè hoặc tạo mới phiên chat.
        - data: Mảng kết quả truy vấn (records) để render bảng trên UI.
        - sql: Câu lệnh SQL đã chạy.
        - chart_config: Cấu hình biểu đồ do AI chọn.
        - narrative: Nhận xét AI tự động.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 1. Lấy memory_json hiện tại
                cursor.execute('SELECT memory_json FROM sessions WHERE session_id = ?', (session_id,))
                row = cursor.fetchone() # trả về một tuple. 
                
                if row:
                    # Session đã tồn tại -> Load mảng JSON cũ
                    try:
                        memory_arr = json.loads(row[0])
                    except json.JSONDecodeError:
                        memory_arr = []
                        
                    # Thêm lượt chat mới
                    memory_arr.append({"role": "user", "content": user_msg})
                    ai_node = {"role": "ai", "content": ai_msg}
                    if chart_json:
                        ai_node["chart_json"] = chart_json
                    if data is not None:
                        ai_node["data"] = data
                    if sql is not None:
                        ai_node["sql"] = sql
                    if chart_config is not None:
                        ai_node["chart_config"] = chart_config
                    if narrative is not None:
                        ai_node["narrative"] = narrative
                    memory_arr.append(ai_node)
                    
                    # Update lại Database
                    new_json_str = json.dumps(memory_arr, ensure_ascii=False) # chuyển dict sang chuỗi json
                    cursor.execute('''  
                        UPDATE sessions 
                        SET memory_json = ?, last_query = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE session_id = ?
                    ''', (new_json_str, user_msg, session_id))
                    
                else:
                    # Session chưa tồn tại -> Khởi tạo mảng JSON mới
                    memory_arr = [
                        {"role": "user", "content": user_msg},
                        {"role": "ai", "content": ai_msg}
                    ]
                    if chart_json:
                        memory_arr[1]["chart_json"] = chart_json
                    if data is not None:
                        memory_arr[1]["data"] = data
                    if sql is not None:
                        memory_arr[1]["sql"] = sql
                    if chart_config is not None:
                        memory_arr[1]["chart_config"] = chart_config
                    if narrative is not None:
                        memory_arr[1]["narrative"] = narrative
                        
                    new_json_str = json.dumps(memory_arr, ensure_ascii=False)
                    cursor.execute('''
                        INSERT INTO sessions (session_id, user_id, memory_json, last_query)
                        VALUES (?, ?, ?, ?)
                    ''', (session_id, user_id, new_json_str, user_msg))
                    
                conn.commit()
        except Exception as e:
            logger.error(f"⚠️ Lỗi ghi memory_json (session: {session_id}): {e}")

    def get_memory(self, session_id: str, limit: int = 5) -> List[Dict[str, str]]:
        """
        Lấy ra mảng lịch sử (chỉ trả về Text để làm Context Window cho AI).
        Không trả về phần chart_json vì AI đọc cái đó sẽ bị rác (Noise).
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT memory_json FROM sessions WHERE session_id = ?', (session_id,))
                row = cursor.fetchone()
                
                if not row:
                    return []
                    
                try:
                    memory_arr = json.loads(row[0]) # chuyển chuỗi json sang list dict
                except json.JSONDecodeError:
                    return []
                
                # Format lại mảng [{role: user, content}, {role: ai, content}] thành format mà NLU mong đợi:
                # [{"user": "câu hỏi", "ai": "câu trả lời"}, ...]
                formatted_history = []
                current_user_msg = None
                
                for msg in memory_arr:
                    role = msg.get("role")
                    content = msg.get("content", "")
                    
                    if role == "user":
                        current_user_msg = content
                    elif role == "ai" and current_user_msg is not None:
                        formatted_history.append({
                            "user": current_user_msg,
                            "ai": content
                        })
                        current_user_msg = None
                        
                # Lấy N lượt gần nhất (1 lượt = 1 user + 1 ai)
                return formatted_history[-limit:] if limit > 0 else formatted_history
                
        except Exception as e:
            logger.error(f"⚠️ Lỗi đọc memory_json (session: {session_id}): {e}")
            return []
            
    def get_full_session(self, session_id: str) -> List[Dict]:
        """
        Lấy toàn bộ mảng JSON nguyên thủy (bao gồm cả chart_json)
        để UI Render (Streamlit) khôi phục giao diện khi F5.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT memory_json FROM sessions WHERE session_id = ?', (session_id,))
                row = cursor.fetchone()
                if row:
                    return json.loads(row[0])
        except Exception as e:
            logger.error(f"⚠️ Lỗi đọc full session: {e}")
        return []

    def clear_session(self, session_id: str):
        """Xóa một phiên chat"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM sessions WHERE session_id = ?', (session_id,))
                conn.commit()
                logger.info(f"🧹 Đã xóa session: {session_id}")
        except Exception as e:
            logger.error(f"⚠️ Lỗi xóa session: {e}")