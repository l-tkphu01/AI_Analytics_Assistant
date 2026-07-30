"""
SQL GENERATOR — Trung tâm Sinh SQL từ Câu hỏi Tiếng Việt (Bước 4A)

Nhận vào:
├── Câu hỏi gốc (original_question)
├── Schema liên quan (từ Vector Search Bước 2)
├── Luật RLS (từ Security Engine Bước 1)
├── JSON NLU (intent, metric, filter... từ NLU Engine Bước 3)
│
▼ Gọi Llama 3.3 70B (qua Groq) viết SQL
│
Output: "SELECT SUM(\"SalesAmount\") FROM \"Fact_Sales\" WHERE \"Quarter\" = 3"

Prompt đọc từ config/prompts.yaml (KHÔNG hardcode).
"""
import yaml
import os
import re
from typing import Dict, Any, Optional
from core.logger import get_logger
from core.llm_providers import LLMProvider

logger = get_logger(__name__)

# Đọc prompts từ file YAML 1 lần duy nhất
def _load_prompts() -> dict:
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config", "prompts.yaml")
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        logger.warning(f"Không đọc được prompts.yaml: {e}")
        return {}

_PROMPTS = _load_prompts()


class SQLGenerator:
    """
    Bộ Sinh SQL: Câu hỏi tiếng Việt + Schema + RLS + NLU → Câu SQL chuẩn.
    Sử dụng Llama 3.3 70B (qua Groq API, miễn phí).
    """

    def __init__(self):
        self._llm = None  # Lazy Loading

    def _get_llm(self):
        """Lazy Loading: Chỉ kết nối Groq khi thật sự cần."""
        if self._llm is None:
            self._llm = LLMProvider.get_sql_llm()
            logger.info("SQL Generator: Đã kết nối Groq Llama 3.3 70B.")
        return self._llm

    def _build_nlu_hint(self, nlu_result: Optional[Dict] = None) -> str:
        """
        Tạo gợi ý từ NLU JSON để Llama viết SQL chính xác hơn.
        Đây chỉ là GỢI Ý BỔ TRỢ, không phải nguồn sự thật duy nhất.
        """
        if not nlu_result or nlu_result.get("intent") == "GENERAL":
            return ""

        hints = []
        intent = nlu_result.get("intent", "")
        metric = nlu_result.get("metric")
        dimension = nlu_result.get("dimension")
        filt = nlu_result.get("filter", {})
        time_range = nlu_result.get("time_range", {})
        limit = nlu_result.get("limit")
        sort = nlu_result.get("sort")

        if intent:
            hints.append(f"- Ý đồ người dùng (Intent): {intent}")
        if metric:
            hints.append(f"- Chỉ số cần tính (Metric): {metric}")
        if dimension:
            hints.append(f"- Chiều phân tích (Dimension/Group By): {dimension}")
        if filt:
            filter_str = ", ".join([f"{k} = '{v}'" for k, v in filt.items()])
            hints.append(f"- Điều kiện lọc (Filter): {filter_str}")
        if time_range:
            time_str = ", ".join([f"{k} = {v}" for k, v in time_range.items() if v])
            if time_str:
                hints.append(f"- Khoảng thời gian (Time Range): {time_str}")
        if limit:
            hints.append(f"- Giới hạn kết quả (LIMIT): {limit}")
        if sort:
            hints.append(f"- Sắp xếp (ORDER BY): {sort}")

        if not hints:
            return ""

        return "\n  --- GỢI Ý TỪ NLU (Tham khảo, không bắt buộc) ---\n  " + "\n  ".join(hints)

    def _clean_sql(self, raw_sql: str) -> str:
        """
        Dọn dẹp SQL trả về từ LLM:
        - Bỏ markdown (```sql...```)
        - Bỏ dấu ; thừa ở cuối
        - Bỏ dòng trống thừa
        """
        sql = raw_sql.strip()

        match = re.search(r'```(?:sql)?\s*(.*?)\s*```', sql, re.IGNORECASE | re.DOTALL)
        if match:
            sql = match.group(1)
         
        sql = sql.strip()

        # Bỏ dấu ; thừa ở cuối
        sql = sql.rstrip(";").strip()

        # Bỏ dòng trống thừa
        sql = re.sub(r'\n\s*\n', '\n', sql)

        return sql

    def generate_sql(
        self,
        question: str,
        schema: str,
        rls_prompt: str = "",
        nlu_result: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Hàm chính: Sinh câu SQL từ câu hỏi tiếng Việt.

        Args:
            question: Câu hỏi gốc (đã qua Rewriting).
            schema: Chuỗi text mô tả Schema (từ SchemaIndexer.get_relevant_schema_for_prompt).
            rls_prompt: Luật bảo mật RLS cần nhét vào WHERE (từ Security Engine).
            nlu_result: JSON từ NLU Engine (intent, metric, filter...).

        Returns:
            Dict gồm:
            - "sql": Câu SQL thuần (str).
            - "success": True/False.
            - "error": Thông báo lỗi nếu có.
        """
        # Đọc prompt template từ YAML
        prompt_template = _PROMPTS.get("sql_system_prompt", "")
        if not prompt_template:
            return {"sql": "", "success": False, "error": "Thiếu sql_system_prompt trong prompts.yaml"}

        # Tạo gợi ý NLU
        nlu_hint = self._build_nlu_hint(nlu_result)

        # Ghép RLS + NLU hint
        full_rls = rls_prompt if rls_prompt else "Không có điều kiện bảo mật."
        if nlu_hint:
            full_rls += f"\n{nlu_hint}"

        # Format prompt
        system_prompt = prompt_template.format(
            schema=schema,
            rls_prompt=full_rls
        )

        # User message = câu hỏi gốc
        user_message = f"Câu hỏi: {question}"

        try:
            llm = self._get_llm()
            response = llm.invoke([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ])

            raw_sql = response.content
            clean_sql = self._clean_sql(raw_sql)

            if not clean_sql:
                return {"sql": "", "success": False, "error": "LLM trả về SQL rỗng."}

            logger.info(f"SQL Generator: Đã sinh SQL thành công ({len(clean_sql)} ký tự).")
            logger.debug(f"SQL: {clean_sql}")

            return {
                "sql": clean_sql,
                "success": True,
                "error": None
            }

        except Exception as e:
            logger.error(f"SQL Generator: Lỗi gọi Groq: {e}")
            return {
                "sql": "",
                "success": False,
                "error": str(e)
            }