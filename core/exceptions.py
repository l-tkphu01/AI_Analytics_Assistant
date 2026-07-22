class AIAnalyticsError(Exception):
    """Lớp base cho tất cả custom exceptions của hệ thống."""
    pass

class NLUError(AIAnalyticsError):
    """Lỗi khi NLU (Gemini) không parse được intent hoặc chặn bởi Guardrail."""
    pass

class SQLGenerationError(AIAnalyticsError):
    """Lỗi khi LLM (Groq) sinh SQL thất bại hoặc vượt quá số lần retry."""
    pass

class SQLValidationError(AIAnalyticsError):
    """Lỗi khi SQL sinh ra vi phạm quy tắc bảo mật (DROP, UPDATE) hoặc RLS."""
    pass

class DatabaseConnectionError(AIAnalyticsError):
    """Lỗi khi không thể kết nối tới Database (Fabric, PostgreSQL)."""
    pass

class RateLimitError(AIAnalyticsError):
    """Lỗi khi gọi API LLM bị quá giới hạn (Rate limit)."""
    pass

class SecurityError(AIAnalyticsError):
    """Lỗi khi user không có quyền truy cập table/schema cụ thể."""
    pass

class SchemaNotFoundError(AIAnalyticsError):
    """Lỗi khi không tìm thấy schema trong ChromaDB."""
    pass

class QueryLimitExceededError(AIAnalyticsError):
    """Lỗi khi câu truy vấn cố tình lấy quá số dòng quy định (Tránh nổ RAM / Bom dữ liệu)."""
    pass

class CacheError(AIAnalyticsError):
    """Lỗi khi thao tác Đọc/Ghi bộ nhớ đệm Local Cache thất bại."""
    pass
