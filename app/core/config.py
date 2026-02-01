from typing import Optional
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Application
    app_name: str = "Translation Agent Service"
    app_version: str = "1.0.0"
    debug: bool = True
    
    # API
    api_prefix: str = "/api/v1"
    api_host: str = "0.0.0.0"
    api_port: int = 8001
    
    # Supabase
    supabase_url: str
    supabase_key: str
    supabase_service_key: str
    database_url: str
    
    # Redis
    redis_url: str = "redis://localhost:6379/1"
    
    # Translation Providers
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    deepl_api_key: Optional[str] = None
    google_application_credentials: Optional[str] = None
    
    # Default Models
    default_gpt_model: str = "gpt-4-turbo-preview"
    default_claude_model: str = "claude-3-opus-20240229"
    default_translation_provider: str = "openai"
    
    # Translation Settings
    max_chunk_size: int = 4000
    translation_timeout: int = 300
    enable_back_translation: bool = True
    confidence_threshold: float = 0.85
    
    # Feature Flags (Epic 4: Surgical Reality)
    enable_real_pdf_parsing: bool = True  # Enabled for demo
    enable_live_llm_inference: bool = True
    
    # Digitization Service
    digitization_service_url: str = "http://localhost:8000/api/v1"
    
    # Security
    secret_key: str
    access_token_expire_minutes: int = 30
    
    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings():
    return Settings()


settings = get_settings()