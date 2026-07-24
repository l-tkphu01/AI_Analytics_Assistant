"""
HYBRID GUARDRAILS - LƯỚI LỌC KÉP BẢO VỆ AI
Tầng 1: Fast Rule-Based Filter (< 1ms, miễn phí)
Tầng 2: AI Semantic Intent Classification (Gemini Flash)

Đã khắc phục 4 lỗ hổng:
1. Fail-Open  → Fail-Closed (Cấu hình trong YAML)
2. False Positives → Business Safe Phrases whitelist
3. Latency → Smart Skip (câu ngắn không cần AI soi)
4. Context Window Attack → Giới hạn độ dài câu hỏi
"""
import yaml
import os
from core.logger import get_logger

logger = get_logger(__name__)

# ============================================================
# BỘ NHỚ ĐỆM (Cache) - Tránh gọi AI lặp lại cho cùng câu hỏi
# ============================================================
_guardrail_cache: dict[str, tuple[bool, str]] = {}
MAX_CACHE_SIZE = 200

def _load_guard_config() -> dict:
    """Đọc file security_guard.yaml để lấy cấu hình bảo vệ."""
    config_path = os.path.join(os.path.dirname(__file__), "..", "..", "config", "security_guard.yaml")
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Không thể đọc file security_guard.yaml: {e}")
        return {"toxic_words": [], "sql_injection_keywords": [], "ai_guardrail": {"enabled": False}}


def _is_business_safe_phrase(question: str, config: dict) -> bool:
    """
    [KHẮC PHỤC LỖ HỔNG #2: FALSE POSITIVES]
    Kiểm tra xem câu hỏi có chứa cụm từ lóng kinh doanh hợp lệ hay không.
    Ví dụ: "hàng chết", "bom hàng", "hủy đơn" → Đây là từ lóng bình thường trong kinh doanh.
    """
    question_lower = question.lower()
    for phrase in config.get("business_safe_phrases", []):
        if phrase in question_lower:
            logger.info(f"✅ Guardrails: Phát hiện cụm từ kinh doanh hợp lệ '{phrase}', bỏ qua kiểm tra từ cấm.")
            return True
    return False


def validate_question_fast(question: str, config: dict) -> tuple[bool, str]:
    """
    TẦNG 1: Fast Rule-Based Filter (< 1ms, Chi phí 0đ)
    Quét từ khóa cấm nguy hiểm và SQL Injection thô bạo.
    [KHẮC PHỤC LỖ HỔNG #2]: Kiểm tra Business Safe Phrases trước khi chặn.
    """
    question_lower = question.lower()
    
    # Bước 0: Kiểm tra cụm từ kinh doanh hợp lệ TRƯỚC
    is_biz_safe = _is_business_safe_phrase(question, config)
    
    # Bước 1: Quét từ ngữ độc hại
    for word in config.get("toxic_words", []):
        if word in question_lower:
            # Nếu câu hỏi chứa cụm từ kinh doanh hợp lệ → Bỏ qua, không chặn
            if is_biz_safe:
                continue
            logger.error(f"🚨 [TẦNG 1] BÁO ĐỘNG: Ngôn từ độc hại '{word}'!")
            return False, f"Phát hiện ngôn từ không phù hợp: '{word}'"
            
    # Bước 2: Quét SQL Injection thô bạo
    for word in config.get("sql_injection_keywords", []):
        if word.lower() in question_lower:
            logger.error(f"🚨 [TẦNG 1] BÁO ĐỘNG: Ý đồ phá hoại CSDL '{word}'!")
            return False, f"Phát hiện cú pháp câu lệnh bị cấm: '{word}'"
            
    return True, "SAFE"


def validate_question_ai(question: str, config: dict) -> tuple[bool, str]:
    """
    TẦNG 2: AI Semantic Guardrail (~100ms, Phân tích Ý đồ bằng Gemini Flash)
    Phát hiện Prompt Injection, Jailbreak, và Hỏi Lạc Đề.
    
    [KHẮC PHỤC LỖ HỔNG #1]: Fail-Closed (Cấu hình trong YAML)
    [KHẮC PHỤC LỖ HỔNG #3]: Smart Skip (câu ngắn bỏ qua AI, dùng Cache)
    [KHẮC PHỤC LỖ HỔNG #4]: Giới hạn độ dài câu hỏi (chống Context Window Attack)
    """
    global _guardrail_cache
    
    ai_cfg = config.get("ai_guardrail", {})
    if not ai_cfg.get("enabled", True):
        return True, "SAFE"
    
    # --- KHẮC PHỤC #4: Chống Context Window Attack ---
    max_len = ai_cfg.get("max_question_length", 500)
    if len(question) > max_len:
        logger.warning(f"🚨 [TẦNG 2] CHẶN: Câu hỏi dài {len(question)} ký tự vượt giới hạn {max_len}!")
        return False, f"Câu hỏi quá dài ({len(question)} ký tự). Giới hạn tối đa là {max_len} ký tự."

    # --- KHẮC PHỤC #3: Smart Skip cho câu quá ngắn ---
    min_len = ai_cfg.get("min_length_for_ai_check", 10)
    if len(question) < min_len:
        logger.info(f"⚡ [TẦNG 2] Smart Skip: Câu hỏi quá ngắn ({len(question)} ký tự), bỏ qua AI check.")
        return True, "SAFE"
    
    # --- KHẮC PHỤC #3: Cache - Không gọi AI lặp lại ---
    cache_key = question.strip().lower()
    if cache_key in _guardrail_cache:
        logger.info(f"⚡ [TẦNG 2] Cache Hit: Đã kiểm tra câu này trước đó rồi.")
        return _guardrail_cache[cache_key]

    # --- GỌI AI GEMINI FLASH ---
    fail_closed = ai_cfg.get("fail_closed", True)
    
    try:
        # Lazy Import: Chỉ nạp thư viện AI khi thực sự cần dùng (tránh lỗi ModuleNotFoundError lúc khởi động)
        from core.llm_providers import LLMProvider
        import json as json_lib
        llm = LLMProvider.get_nlu_llm()
        system_prompt = ai_cfg.get("system_prompt", "")
        
        messages = [
            ("system", system_prompt),
            ("human", f"Câu hỏi từ người dùng: '{question}'")
        ]
        
        response = llm.invoke(messages)
        raw = response.content.strip()
        
        logger.info(f"🧠 [TẦNG 2] AI Guardrail phản hồi: '{raw}' cho câu hỏi: '{question[:80]}...'")
        
        # Thử parse JSON từ AI (AI trả về {"verdict": "...", "message": "..."})
        try:
            parsed = json_lib.loads(raw)
            verdict = parsed.get("verdict", "SAFE").upper()
            ai_message = parsed.get("message", "")
        except (json_lib.JSONDecodeError, AttributeError):
            # Nếu AI trả về text thuần (không phải JSON), dùng logic cũ
            verdict = raw.upper()
            ai_message = ""
        
        if "UNSAFE" in verdict:
            logger.warning(f"🚨 [TẦNG 2] AI CHẶN câu hỏi không an toàn!")
            friendly_msg = ai_message if ai_message else "AI phát hiện ý đồ không an toàn hoặc vi phạm tiêu chuẩn cộng đồng."
            answer = (False, friendly_msg)
        elif "OUT_OF_SCOPE" in verdict:
            logger.warning(f"⚠️ [TẦNG 2] AI CHẶN câu hỏi lạc đề!")
            friendly_msg = ai_message if ai_message else "Câu hỏi không nằm trong phạm vi phân tích dữ liệu doanh nghiệp."
            answer = (False, friendly_msg)
        else:
            answer = (True, "SAFE")
        
        # Lưu vào Cache
        if len(_guardrail_cache) >= MAX_CACHE_SIZE:
            _guardrail_cache.clear()
        _guardrail_cache[cache_key] = answer
        
        return answer
        
    except Exception as e:
        # --- KHẮC PHỤC #1: Fail-Closed ---
        logger.error(f"⚠️ Lỗi khi gọi AI Guardrail Tầng 2: {e}")
        if fail_closed:
            logger.warning("🔒 [FAIL-CLOSED] AI lỗi → CHẶN TẤT CẢ để đảm bảo an toàn tuyệt đối!")
            return False, "Hệ thống bảo mật AI đang tạm thời không khả dụng. Vui lòng thử lại sau."
        else:
            logger.warning("🔓 [FAIL-OPEN] AI lỗi → Cho qua (Chế độ ưu tiên trải nghiệm người dùng).")
            return True, "SAFE"


def validate_question_safety(question: str) -> tuple[bool, str]:
    """
    MASTER HYBRID GUARDRAIL:
    Chạy Tầng 1 (Fast Filter) → Nếu qua → Chạy Tầng 2 (AI Semantic Filter).
    """
    config = _load_guard_config()
    
    # Tầng 1: Rule-based (< 1ms)
    is_safe_t1, msg_t1 = validate_question_fast(question, config)
    if not is_safe_t1:
        return False, msg_t1
        
    # Tầng 2: AI Semantic (~100ms)
    is_safe_t2, msg_t2 = validate_question_ai(question, config)
    if not is_safe_t2:
        return False, msg_t2
        
    return True, "SAFE"