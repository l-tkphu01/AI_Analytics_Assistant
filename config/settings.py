import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal

class Settings(BaseSettings):
    # LLM
    OPENROUTER_API_KEY: str = ""
    GROQ_API_KEY: str = ""
    COHERE_API_KEY: str = ""
     
    # Data Source
    DATA_SOURCE: Literal["fabric", "postgresql", "sqlite"] = "sqlite"
    
    # Fabric (Đã vá: Thêm Tenant ID để xác thực Service Principal)
    FABRIC_SQL_ENDPOINT: str = ""
    FABRIC_DATABASE: str = ""
    FABRIC_CLIENT_ID: str = ""
    FABRIC_CLIENT_SECRET: str = ""
    FABRIC_TENANT_ID: str = "" 
    
    # PostgreSQL / Supabase
    DATABASE_URL: str = ""
    SUPABASE_URL: str = ""
    SUPABASE_KEY: str = ""
    
    # Security
    JWT_SECRET_KEY: str = "default_secret_key"
    JWT_ALGORITHM: str = "HS256"
    
    # App Config (Đã vá: Thêm biến môi trường và Công tắc gỡ lỗi)
    ENVIRONMENT: Literal["dev", "staging", "prod"] = "dev"
    DEBUG: bool = True 
    CACHE_TTL: int = 300
    MAX_QUERY_ROWS: int = 50000
    QUERY_TIMEOUT: int = 30
    LOG_LEVEL: str = "INFO"
    
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

# Singleton instance
settings = Settings()

# Mapping data source to SQL dialect
SQL_DIALECT_MAP = {
    "fabric": "T-SQL",
    "postgresql": "PostgreSQL",
    "sqlite": "SQLite"
}

def get_sql_dialect() -> str:
    """Trả về dialect tương ứng với nguồn dữ liệu hiện tại."""
    return SQL_DIALECT_MAP.get(settings.DATA_SOURCE, "SQLite")