"""
NLU ENGINE — Trung tâm Phân tích Ý đồ Người dùng (Bước 3)
Nhận câu hỏi tiếng Việt bất kỳ → Gọi Gemini Flash Lite → Trả về JSON chuẩn.

THIẾT KẾ ĐÃ VÁ 3 ĐIỂM CHÊ:
1. Nhồi danh sách Bảng + Cột vào Prompt → Gemini không bịa tên cột.
2. Dùng Gemini Flash Lite siêu rẻ (~0.5s).
3. Fallback: Nếu Gemini trả JSON lỗi → Trả intent mặc định GENERAL.
"""
import json
import yaml
import os
import re
from typing import Dict, Any, List, Optional
from core.logger import get_logger
from core.llm_providers import LLMProvider

logger = get_logger(__name__)

# Đọc prompts từ file YAML 1 lần duy nhất (không hardcode!)
def _load_prompts() -> dict:
    """Đọc toàn bộ prompt từ config/prompts.yaml."""
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config", "prompts.yaml")
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        logger.warning(f"Không đọc được prompts.yaml: {e}. Dùng prompt mặc định.")
        return {}

_PROMPTS = _load_prompts() # Đọc một lần duy nhất tại module load, lưu toàn bộ các câu prompt vào một biến toàn cục _PROMPTS

# Danh sách Intent hợp lệ (AI chỉ được chọn 1 trong những loại này)
VALID_INTENTS = [
    "AGGREGATION",   # Tổng hợp: tổng, trung bình, đếm (SUM, AVG, COUNT)
    "RANKING",       # Xếp hạng: top 5, cao nhất, thấp nhất (ORDER BY + LIMIT)
    "COMPARISON",    # So sánh: so sánh giữa 2+ nhóm (GROUP BY)
    "TREND",         # Xu hướng: theo thời gian, biến động (GROUP BY time)
    "DETAIL",        # Chi tiết: liệt kê dữ liệu thô (SELECT *)
    "METADATA",      # Hỏi về cấu trúc: có bảng nào, cột nào, ý nghĩa là gì
    "GENERAL",       # Câu hỏi chung chung, không rõ ý đồ
]

# Hàm tạo JSON mặc định khi Gemini lỗi hoặc trả kết quả không hợp lệ (Chống lỗi Shallow Copy)
def get_default_nlu_result() -> Dict[str, Any]:
    return {
        "intent": "GENERAL",
        "metric": None,
        "dimension": None,
        "filter": {},
        "time_range": {},
        "limit": None,
        "sort": None,
        "original_question": ""
    }


class NLUEngine:
    """
    Bộ Thông dịch viên: Dịch câu hỏi tiếng Việt → JSON cấu trúc.
    Sử dụng Gemini Flash Lite (siêu rẻ, siêu nhanh) qua OpenRouter.
    """

    def __init__(self):
        self._llm = None  # Lazy Loading: Chỉ kết nối Gemini khi thật sự cần

    def _get_llm(self):
        """Lazy Loading: Khởi tạo LLM lần đầu tiên khi được gọi."""
        if self._llm is None:
            self._llm = LLMProvider.get_nlu_llm()
            logger.info("NLU Engine: Đã kết nối Gemini Flash Lite.")
        return self._llm

    def rewrite_question(self, current_question: str, chat_history: List[Dict] = None) -> List[str]:
        """
        [REWRITING & QUERY EXPANSION]
        Viết lại câu hỏi từ 1 câu → 3 câu đa dạng ngữ cảnh để tối ưu Vector Search.
        
        Returns:
            List gồm 3 câu hỏi đã được mở rộng.
        """
        # Nếu không có lịch sử chat thì vẫn có thể làm Query Expansion được,
        # nên ta bỏ logic "if not chat_history return current_question" ở đây,
        # nhưng ta chỉ lấy chat_history nếu có.
        history_text = "Không có lịch sử."
        if chat_history:
            recent_history = chat_history[-3:] if len(chat_history) > 3 else chat_history
            history_text = ""
            for msg in recent_history:
                if "user" in msg and "ai" in msg:
                    history_text += f"  User: {msg['user']}\n  AI: {msg['ai']}\n"
                elif "role" in msg and "content" in msg:
                    # Tương thích ngược nếu data có dạng role/content
                    role = "User" if msg.get("role") == "user" else "AI"
                    history_text += f"  {role}: {msg.get('content', '')}\n"

        # Đọc prompt từ YAML thay vì hardcode
        prompt_template = _PROMPTS.get("nlu_rewrite_prompt", "Viết lại câu hỏi thành 3 câu JSON Array:\n{chat_history}\n{question}")
        prompt = prompt_template.format(
            chat_history=history_text,
            question=current_question
        )

        try:
            llm = self._get_llm()
            response = llm.invoke(prompt)
            content = response.content.strip()

            # Tiền xử lý bỏ markdown bằng RegEx (tìm khối [...] cho Array)
            match = re.search(r'\[.*\]', content, re.DOTALL)
            if match:
                content = match.group(0)
            else:
                content = content.strip()

            result = json.loads(content)
            
            if isinstance(result, list) and len(result) > 0:
                logger.info(f"NLU Query Expansion: '{current_question}' → {len(result)} biến thể.")
                return result
            else:
                return [current_question]

        except json.JSONDecodeError as e:
            logger.warning(f"NLU Rewrite JSON lỗi: {e}. Trả về câu gốc. Content: {content[:100]}")
            return [current_question]
        except Exception as e:
            logger.warning(f"NLU Rewrite lỗi: {e}. Giữ nguyên câu gốc.")
            return [current_question]

    def _build_schema_hint(self, schema_columns: List[Dict[str, Any]]) -> str:
        """
        Tạo danh sách Bảng + Cột để nhồi vào Prompt.
        Giúp Gemini chỉ được chọn từ danh sách có sẵn, không được bịa tên.
        Tích hợp CLS: Cắt bỏ hoàn toàn các cột thuộc diện "exclude" khỏi Schema.
        """
        if not schema_columns:
            return "Không có thông tin schema."
            
        # Lấy danh sách cột bị cấm (exclude) từ CLS Manager (Singleton - import 1 lần)
        from modules.security.cls import CLSManager
        _cls_instance = CLSManager._instance if hasattr(CLSManager, '_instance') else CLSManager()
        exclude_cols = _cls_instance.exclude_columns

        hint = ""
        for table in schema_columns:
            t_name = table["table_name"]
            # Chỉ lấy các cột KHÔNG nằm trong danh sách exclude
            cols = [col["name"] for col in table["columns"] if col["name"].lower() not in exclude_cols]
            
            if cols: # Nếu bảng còn cột (không bị cấm hết) thì mới thêm vào hint
                hint += f"- Bảng '{t_name}': Các cột [{', '.join(cols)}]\n"
        return hint

    def analyze_intent(self, question: str, schema_columns: Optional[List[Dict]] = None) -> Dict[str, Any]:
        """
        Hàm chính: Phân tích ý đồ người dùng từ câu hỏi tiếng Việt.
        
        Args:
            question: Câu hỏi tiếng Việt gốc từ user.
            schema_columns: Danh sách schema đã prune (để Gemini biết DB có gì).
        
        Returns:
            Dict chứa: intent, metric, dimension, filter, time_range, limit, sort.
        """
        # Tạo danh sách schema cho Prompt
        schema_hint = self._build_schema_hint(schema_columns) if schema_columns else "Không có thông tin schema."

        # Đọc prompt từ YAML (Không dùng câu dự phòng nữa để ép lỗi Fail-Fast)
        prompt_template = _PROMPTS.get("nlu_intent_prompt")
        
        if not prompt_template:
            raise ValueError("Toang rồi sếp! File prompts.yaml bị mất đoạn nlu_intent_prompt rồi!")
        
        prompt = prompt_template.format(
            schema_hint=schema_hint,
            question=question
        )

        try:
            llm = self._get_llm()
            response = llm.invoke(prompt)
            content = response.content.strip()

            # Tiền xử lý: Dùng RegEx tìm chính xác khối JSON {...}
            match = re.search(r'\{.*\}', content, re.DOTALL)
            if match:
                content = match.group(0)
            else:
                content = content.strip()

            # Parse JSON
            result = json.loads(content)

            # Validate intent hợp lệ
            if result.get("intent") not in VALID_INTENTS:
                logger.warning(f"NLU: Intent '{result.get('intent')}' không hợp lệ. Chuyển về GENERAL.")
                result["intent"] = "GENERAL"

            # Gắn câu hỏi gốc vào kết quả để các bước sau có thể dùng
            result["original_question"] = question

            # Đảm bảo tất cả field đều tồn tại (tránh KeyError ở bước sau)
            default_res = get_default_nlu_result()
            for key in default_res:
                if key not in result:
                    result[key] = default_res[key]

            logger.info(f"NLU Engine: Intent={result['intent']} | Metric={result.get('metric')} | Dimension={result.get('dimension')}")
            return result

        except json.JSONDecodeError as e:
            logger.error(f"NLU Engine: Gemini trả JSON lỗi: {e}. Nội dung: {content[:200] if 'content' in locals() else 'N/A'}")
            fallback = get_default_nlu_result()
            fallback["original_question"] = question
            return fallback

        except Exception as e:
            logger.error(f"NLU Engine: Lỗi gọi Gemini: {e}")
            fallback = get_default_nlu_result()
            fallback["original_question"] = question
            return fallback