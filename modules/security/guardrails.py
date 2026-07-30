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
import re
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
        return {"toxic_words": [], "ai_guardrail": {"enabled": False}}


def _mask_business_safe_phrases(question: str, config: dict) -> str:
    """
    [KHẮC PHỤC LỖ HỔNG #2: FALSE POSITIVES & RACE CONDITION]
    Che (mask) các cụm từ kinh doanh hợp lệ trước khi quét Blacklist.
    Tránh việc user lợi dụng Whitelist để chèn từ cấm (Vd: "muốn đánh thằng kia vì đánh giá tệ").
    """
    masked_question = question
    for phrase in config.get("business_safe_phrases", []):
        # Dùng regex ignore case để thay thế cụm từ an toàn bằng [SAFE_PHRASE]
        # Regex re.escape giúp tránh lỗi nếu phrase có chứa ký tự đặc biệt
        pattern = re.compile(re.escape(phrase), re.IGNORECASE)
        if pattern.search(masked_question):
            masked_question = pattern.sub(" [SAFE_PHRASE] ", masked_question)
            logger.info(f"✅ Guardrails: Đã che cụm từ kinh doanh hợp lệ '{phrase}'.")
            
    return masked_question


def _normalize_and_tokenize(text: str) -> tuple[str, set]:
    """Làm sạch câu hỏi (xóa dấu câu) và tách thành tập hợp các từ (tokens)."""
    # Xóa các ký tự đặc biệt, dấu câu, chỉ giữ lại chữ cái, số và khoảng trắng
    # Lưu ý: Giữ lại cả dấu ngoặc vuông để không xóa mất chữ [SAFE_PHRASE]
    clean_text = re.sub(r'[^\w\s\[\]]', ' ', text.lower())
    # Chuẩn hóa khoảng trắng
    clean_text = re.sub(r'\s+', ' ', clean_text).strip()
    # Tách thành mảng các từ
    tokens = set(clean_text.split())
    return clean_text, tokens


def validate_question_fast(question: str, config: dict) -> tuple[bool, str]:
    """
    TẦNG 1: Fast Rule-Based Filter (< 1ms, Chi phí 0đ)
    Quét từ khóa cấm nguy hiểm và SQL Injection thô bạo.
    """
    # Bước 0: MASKING (Che) cụm từ kinh doanh hợp lệ TRƯỚC
    # Biến câu "Tôi muốn đánh đứa đánh giá tệ" thành "Tôi muốn đánh đứa [SAFE_PHRASE] tệ"
    masked_question = _mask_business_safe_phrases(question, config)
    
    # Chuẩn bị dữ liệu từ câu đã được che (Tokenization/Normalization)
    clean_text, tokens = _normalize_and_tokenize(masked_question)
    
    # Bước 1: Quét từ ngữ độc hại trên câu ĐÃ CHE
    for word in config.get("toxic_words", []):
        toxic_word = word.lower().strip()
        matched = False
        
        # Nếu từ cấm là một cụm từ (có khoảng trắng) -> dùng substring match an toàn
        if " " in toxic_word:
            if f" {toxic_word} " in f" {clean_text} ":
                matched = True
        # Nếu từ cấm là từ đơn -> check trong tập tokens (O(1))
        else:
            if toxic_word in tokens:
                matched = True
                
        if matched:
            logger.error(f"🚨 [TẦNG 1] BÁO ĐỘNG: Phát hiện ngôn từ độc hại '{toxic_word}'!")
            return False, "Phát hiện ngôn từ không phù hợp trong câu hỏi."
            
    return True, "SAFE"


def validate_question_ai(question: str, config: dict, chat_history: list = None) -> tuple[bool, str]:
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
            ("system", system_prompt)
        ]
        
        # Nhúng lịch sử chat (Multi-turn Context)
        if chat_history:
            history_text = "LỊCH SỬ CHAT (Đọc để hiểu ngữ cảnh, phòng chống Jailbreak):\n"
            for turn in chat_history[-3:]: # Lấy 3 lượt gần nhất
                history_text += f"- User: {turn['user']}\n- AI: {turn['ai']}\n"
            messages.append(("human", history_text))
            
        messages.append(("human", f"CÂU HỎI HIỆN TẠI TỪ USER (Cần đánh giá an toàn):\n'{question}'"))
        
        response = llm.invoke(messages)
        raw = response.content.strip()
        
        logger.info(f"🧠 [TẦNG 2] AI Guardrail phản hồi: '{raw}' cho câu hỏi: '{question[:80]}...'")
        
        # Thử parse JSON từ AI (AI trả về {"verdict": "...", "message": "..."})
        try:
            # Xóa bỏ các thẻ markdown (nếu có)
            clean_raw = raw
            match = re.search(r'```(?:json)?\s*(.*?)\s*```', clean_raw, re.IGNORECASE | re.DOTALL)
            if match:
                clean_raw = match.group(1).strip()
                
            parsed = json_lib.loads(clean_raw)
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
            logger.critical("🚨 [ALERT] AI Guardrail SẬP! Triggering PagerDuty/Slack alert!")
            logger.warning("🔒 [FAIL-CLOSED] AI lỗi → CHẶN TẤT CẢ để đảm bảo an toàn tuyệt đối!")
            return False, "Hệ thống bảo mật AI đang tạm thời không khả dụng. Vui lòng thử lại sau."
        else:
            logger.warning("🔓 [FAIL-OPEN] AI lỗi → Cho qua (Chế độ ưu tiên trải nghiệm người dùng).")
            return True, "SAFE"


def validate_question_safety(question: str, chat_history: list = None) -> tuple[bool, str]:
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
    is_safe_t2, msg_t2 = validate_question_ai(question, config, chat_history=chat_history)
    if not is_safe_t2:
        return False, msg_t2
        
    return True, "SAFE"