"""
LLM PROVIDERS - TRUNG TÂM ĐIỀU PHỐI AI (Config-Driven)
Toàn bộ tên Model, Temperature, Max Tokens đều đọc từ config/model_params.yaml.
Muốn đổi sang Claude hay GPT-4o? Chỉ sửa file YAML, không cần sửa code Python!
"""
import os
import yaml
from langchain_openai import ChatOpenAI
from langchain_groq import ChatGroq
from langchain_cohere import CohereEmbeddings, CohereRerank
from langchain_community.embeddings import HuggingFaceEmbeddings
from config.settings import settings

# ============================================================
# ĐỌC CẤU HÌNH TỪ YAML (1 LẦN DUY NHẤT KHI KHỞI ĐỘNG)
# ============================================================
_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "model_params.yaml")

def _load_model_params() -> dict:
    """Đọc file model_params.yaml để lấy tham số cho các mô hình AI."""
    try:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception as e:
        # Nếu file bị hỏng, trả về giá trị mặc định an toàn
        print(f"⚠️ Không thể đọc model_params.yaml: {e}. Dùng giá trị mặc định.")
        return {}

# Nạp 1 lần lúc import, không đọc lại mỗi lần gọi hàm
_PARAMS = _load_model_params()


class LLMProvider:
    """Class quản lý toàn bộ các Models AI được dùng trong hệ thống (Config-Driven)."""
    
    @staticmethod
    def get_nlu_llm():
        """
        Model cho NLU (Natural Language Understanding) và Guardrails Tầng 2.
        Mặc định: Gemini Flash (thông qua OpenRouter API).
        """
        cfg = _PARAMS.get("nlu_model", {})
        if not settings.OPENROUTER_API_KEY:
            raise ValueError("Thiếu OPENROUTER_API_KEY trong file .env")
            
        return ChatOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=settings.OPENROUTER_API_KEY,
            model=cfg.get("model_name", "google/gemini-2.5-flash-lite"),
            temperature=cfg.get("temperature", 0.1),
            max_tokens=cfg.get("max_tokens", 500),
            request_timeout=cfg.get("request_timeout", 10),
        )
         
    @staticmethod
    def get_sql_llm():
        """
        Model cho việc sinh code SQL (Text-to-SQL).
        Mặc định: Groq Llama 3.3 70B.
        """
        cfg = _PARAMS.get("sql_model", {})
        if not settings.GROQ_API_KEY:
            raise ValueError("Thiếu GROQ_API_KEY trong file .env")
            
        return ChatGroq(
            model_name=cfg.get("model_name", "llama-3.3-70b-versatile"),
            groq_api_key=settings.GROQ_API_KEY,
            temperature=cfg.get("temperature", 0.0),
            max_tokens=cfg.get("max_tokens", 1500),
            request_timeout=cfg.get("request_timeout", 15),
        )
         
    @staticmethod
    def get_correction_llm():
        """
        Model siêu cấp (Claude/GPT-4o) dùng để sửa lỗi SQL hoặc phân tích dữ liệu phức tạp.
        Đọc từ config 'correction_model'.
        """
        cfg = _PARAMS.get("correction_model", {})
        
        # Nếu dùng OpenRouter (như Claude 3.5 Sonnet)
        if cfg.get("provider") == "openrouter":
            if not settings.OPENROUTER_API_KEY:
                raise ValueError("Thiếu OPENROUTER_API_KEY trong file .env")
            return ChatOpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=settings.OPENROUTER_API_KEY,
                model=cfg.get("model_name", "openai/gpt-4o-mini"),
                temperature=cfg.get("temperature", 0.1),
                max_tokens=cfg.get("max_tokens", 1000),
                request_timeout=cfg.get("request_timeout", 15),
            )
        # Fallback về Groq (Llama) nếu không dùng OpenRouter
        else:
            if not settings.GROQ_API_KEY:
                raise ValueError("Thiếu GROQ_API_KEY trong file .env")
            return ChatGroq(
                model_name=cfg.get("model_name", "llama-3.3-70b-versatile"),
                groq_api_key=settings.GROQ_API_KEY,
                temperature=cfg.get("temperature", 0.1),
                max_tokens=cfg.get("max_tokens", 1000),
                request_timeout=cfg.get("request_timeout", 15),
            )

         
    @staticmethod
    def get_analysis_llm():
        """
        Model cho việc sinh Báo cáo phân tích chuyên gia (Narrative).
        Mặc định: Gemini Flash, nhiệt độ cao hơn để văn phong mượt mà.
        """ 
        cfg = _PARAMS.get("analysis_model", {})
        if not settings.OPENROUTER_API_KEY:
            raise ValueError("Thiếu OPENROUTER_API_KEY trong file .env")
            
        return ChatOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=settings.OPENROUTER_API_KEY,
            model=cfg.get("model_name", "google/gemini-2.5-flash-lite"),
            temperature=cfg.get("temperature", 0.3),
            max_tokens=cfg.get("max_tokens", 2000),
            request_timeout=cfg.get("request_timeout", 15),
        )

    @staticmethod
    def get_embedding_model():
        """
        Model cho quá trình Embedding Schema vào ChromaDB.
        Mặc định: Cohere Multilingual v3 (hỗ trợ tiếng Việt).
        """
        cfg = _PARAMS.get("embedding_model", {})
        if not settings.COHERE_API_KEY:
            raise ValueError("Thiếu COHERE_API_KEY trong file .env")
            
        return CohereEmbeddings(
            model=cfg.get("model_name", "embed-multilingual-v3.0"),
            cohere_api_key=settings.COHERE_API_KEY
        )
        
    @staticmethod
    def get_fallback_embedding_model():
        """
        Lốp dự phòng (Fallback): Dùng khi Cohere API bị lỗi/quá tải.
        Sử dụng mô hình Local chạy siêu nhẹ offline bằng CPU.
        """
        cfg = _PARAMS.get("fallback_embedding_model", {})
        return HuggingFaceEmbeddings(
            model_name=cfg.get("model_name", "all-MiniLM-L6-v2")
        )
        
    @staticmethod
    def get_reranker_model():
        """
        Model dùng để Rerank (chấm điểm tinh lọc Top N kết quả từ ChromaDB).
        Mặc định: Cohere Rerank v3.
        """
        cfg = _PARAMS.get("reranker_model", {})
        if not settings.COHERE_API_KEY:
            raise ValueError("Thiếu COHERE_API_KEY trong file .env cho Reranker")
            
        return CohereRerank(
            cohere_api_key=settings.COHERE_API_KEY,
            model=cfg.get("model_name", "rerank-multilingual-v3.0"),
            top_n=cfg.get("top_n", 3)
        )
