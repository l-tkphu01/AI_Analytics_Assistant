"""
SELF-CORRECTION — AI Tự Sửa Lỗi SQL (Bước 4C)

Luồng chạy:
SQL → Chạy vào DB → Lỗi!
  → Ném (SQL cũ + Schema + Lỗi) cho AI viết lại
  → SQL mới → Chạy lại → OK!
  (Tối đa 3 lần retry)

Prompt đọc từ config/prompts.yaml (KHÔNG hardcode).
"""
import re
import yaml
import os
import pandas as pd
from typing import Dict, Any, Optional
from core.logger import get_logger
from core.llm_providers import LLMProvider

logger = get_logger(__name__)

# Đọc prompts từ YAML 1 lần duy nhất
def _load_prompts() -> dict:
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config", "prompts.yaml")
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        logger.warning(f"Không đọc được prompts.yaml: {e}")
        return {}

_PROMPTS = _load_prompts()


class SelfCorrection:
    """
    AI Tự Sửa Lỗi: Khi SQL chạy lỗi trên DB → Gửi lỗi cho AI viết lại → Thử lại.
    Sử dụng Llama 3.3 70B (qua Groq) để sửa SQL. 
    """

    def __init__(self, connector=None):
        """
        Args:
            connector: DataConnector (PostgreSQL/SQLite) để chạy SQL.
                       Nếu None, sẽ tự khởi tạo PostgreSQLConnector.
        """
        self._llm = None  # Lazy Loading
        self._connector = connector

    def _get_llm(self):
        """Lazy Loading: Dùng correction_model (Groq Llama 3.3 70B)."""
        if self._llm is None:
            # Dùng chung sql_model vì correction_model cũng là Llama 3.3
            self._llm = LLMProvider.get_sql_llm()
            logger.info("Self-Correction: Đã kết nối Groq Llama 3.3 70B.")
        return self._llm

    def _get_connector(self):
        """Lazy Loading: Khởi tạo DB connector nếu chưa có."""
        if self._connector is None:
            from modules.data_source.postgresql import PostgreSQLConnector
            self._connector = PostgreSQLConnector()
            self._connector.connect()
            logger.info("Self-Correction: Đã kết nối PostgreSQL.")
        return self._connector

    def _clean_sql(self, raw_sql: str) -> str:
        """Dọn dẹp SQL trả về từ LLM."""
        sql = raw_sql.strip()
        # Dùng RegEx cắt khối SQL an toàn
        match = re.search(r'```(?:sql)?\s*(.*?)\s*```', sql, re.IGNORECASE | re.DOTALL)
        if match:
            sql = match.group(1)
        
        sql = sql.strip().rstrip(";").strip()
        sql = re.sub(r'\n\s*\n', '\n', sql)
        return sql

    def _ask_ai_to_fix(self, broken_sql: str, error_message: str, schema: str = "") -> str:
        """
        Gửi SQL lỗi + Thông báo lỗi cho AI viết lại.
        
        Returns:
            Câu SQL đã được sửa.
        """
        correction_prompt = _PROMPTS.get("correction_system_prompt", "Sửa SQL bị lỗi.")

        user_message = f"""--- CÂU SQL BỊ LỖI ---
{broken_sql}

--- THÔNG BÁO LỖI TỪ DATABASE ---
{error_message}

--- SCHEMA (Tham khảo) ---
{schema if schema else 'Không có thông tin schema.'}

Hãy viết lại câu SQL cho đúng. CHỈ TRẢ VỀ SQL THUẦN, KHÔNG GIẢI THÍCH."""

        llm = self._get_llm()
        response = llm.invoke([
            {"role": "system", "content": correction_prompt},
            {"role": "user", "content": user_message}
        ])

        return self._clean_sql(response.content)

    def execute_with_retry(
        self,
        sql: str,
        schema: str = "",
        max_retries: int = 3,
    ) -> Dict[str, Any]:
        """
        Hàm chính: Chạy SQL vào DB. Nếu lỗi → AI sửa → Chạy lại.
        
        Args:
            sql: Câu SQL ban đầu (đã qua Validator).
            schema: Schema text (để AI tham khảo khi sửa).
            max_retries: Số lần thử tối đa (mặc định 3).
        
        Returns:
            {
                "success": True/False,
                "data": DataFrame kết quả (nếu thành công),
                "sql_final": Câu SQL cuối cùng đã chạy thành công,
                "retries": Số lần retry đã dùng,
                "error": Thông báo lỗi (nếu thất bại hoàn toàn)
            }
        """
        connector = self._get_connector()
        current_sql = sql
        last_error = None

        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"Self-Correction: Lần thử {attempt}/{max_retries}...")
                logger.debug(f"SQL: {current_sql}")

                # Chạy SQL vào DB
                df = connector.execute(current_sql)

                # Thành công!
                logger.info(f"Self-Correction: SQL chạy thành công ở lần thử {attempt}! ({len(df)} dòng)")
                return {
                    "success": True,
                    "data": df,
                    "sql_final": current_sql,
                    "retries": attempt - 1,
                    "error": None
                }

            except Exception as e:
                last_error = str(e)
                logger.warning(f"Self-Correction: Lần thử {attempt} THẤT BẠI — {last_error}")

                # Nếu còn cơ hội retry → Nhờ AI sửa
                if attempt < max_retries:
                    try:
                        logger.info(f"Self-Correction: Nhờ AI sửa SQL (lần {attempt})...")
                        fixed_sql = self._ask_ai_to_fix(current_sql, last_error, schema)
                        
                        if fixed_sql and fixed_sql != current_sql:
                            logger.info(f"Self-Correction: AI đã viết lại SQL mới.")
                            current_sql = fixed_sql
                        else:
                            logger.warning("Self-Correction: AI trả về SQL giống cũ hoặc rỗng. Dừng retry.")
                            break
                    except Exception as fix_error:
                        logger.error(f"Self-Correction: Lỗi khi nhờ AI sửa: {fix_error}")
                        break

        # Hết cơ hội retry
        logger.error(f"Self-Correction: Đã thử {max_retries} lần nhưng vẫn lỗi. Bó tay!")
        return {
            "success": False,
            "data": None,
            "sql_final": current_sql,
            "retries": max_retries,
            "error": f"SQL vẫn lỗi sau {max_retries} lần thử. Lỗi cuối: {last_error}"
        }