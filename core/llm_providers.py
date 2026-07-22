import os
from langchain_openai import ChatOpenAI
from langchain_groq import ChatGroq
from langchain_cohere import CohereEmbeddings, CohereRerank
from core.exceptions import RateLimitError
from config.settings import settings
from langchain_community.embeddings import HuggingFaceEmbeddings

class LLMProvider:
    """Class quản lý toàn bộ các Models AI được dùng trong hệ thống (Abstraction Layer)."""
    
    @staticmethod
    def get_nlu_llm():
        """
        Model cho NLU (Natural Language Understanding) và check Guardrail.
        Dùng Gemini Flash (thông qua OpenRouter API).
        """
        if not settings.OPENROUTER_API_KEY:
            raise ValueError("Thiếu OPENROUTER_API_KEY trong file .env")
            
        return ChatOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=settings.OPENROUTER_API_KEY,
            model="google/gemini-2.5-flash-lite", 
            temperature=0.0, # NLU cần chính xác tuyệt đối, không sáng tạo
        )
         
    @staticmethod
    def get_sql_llm():
        """
        Model cho việc sinh code SQL (Text-to-SQL).
        Dùng Groq Llama-3-70B: Tốc độ siêu tốc, suy luận code logic cực tốt.
        """
        if not settings.GROQ_API_KEY:
            raise ValueError("Thiếu GROQ_API_KEY trong file .env")
            
        return ChatGroq(
            model_name="llama-3.3-70b-versatile",
            groq_api_key=settings.GROQ_API_KEY,
            temperature=0.0, # SQL cần độ chính xác cao tuyệt đối
        )
         
    @staticmethod
    def get_analysis_llm():
        """
        Model cho việc sinh Báo cáo phân tích chuyên gia (Narrative).
        Vẫn dùng Gemini Flash (qua OpenRouter) nhưng nhiệt độ cao hơn chút để văn phong mượt mà tự nhiên.
        """ 
        if not settings.OPENROUTER_API_KEY:
            raise ValueError("Thiếu OPENROUTER_API_KEY trong file .env")
            
        return ChatOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=settings.OPENROUTER_API_KEY,
            model="google/gemini-2.5-flash-lite",
            temperature=0.3,
        )

    @staticmethod
    def get_embedding_model():
        """
        Model cho quá trình Embedding Schema vào ChromaDB.
        Dùng Cohere Embedding (chuyên gia về xử lý ngôn ngữ đa ngữ và tiếng Việt).
        """
        if not settings.COHERE_API_KEY:
            raise ValueError("Thiếu COHERE_API_KEY trong file .env")
            
        return CohereEmbeddings(
            model="embed-multilingual-v3.0",
            cohere_api_key=settings.COHERE_API_KEY
        )
        
    @staticmethod
    def get_fallback_embedding_model():
        """
        Lốp dự phòng (Fallback): Dùng khi Cohere API bị lỗi/quá tải.
        Sử dụng mô hình Local chạy siêu nhẹ offline bằng CPU.
        """
        return HuggingFaceEmbeddings(
            model_name="all-MiniLM-L6-v2"
        )
        
    @staticmethod
    def get_reranker_model():
        """
        Model dùng để Rerank (chấm điểm tinh lọc Top 10 -> Top 3 kết quả từ ChromaDB).
        Dùng Cohere Rerank API (chung key với Embedding).
        """
        if not settings.COHERE_API_KEY:
            raise ValueError("Thiếu COHERE_API_KEY trong file .env cho Reranker")
            
        return CohereRerank(
            cohere_api_key=settings.COHERE_API_KEY,
            model="rerank-multilingual-v3.0", # Hỗ trợ tiếng Việt siêu đỉnh
            top_n=3 # Chỉ lấy 3 Bảng/Cột chuẩn nhất
        )
