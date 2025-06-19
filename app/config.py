"""
Configuration management for the Farmer AI Pipeline
Handles environment variables and application settings
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, List
import os


class Settings(BaseSettings):
    """Application settings with environment variable support"""
    
    # Application
    app_name: str = "Farmer AI Pipeline"
    version: str = "1.0.0"
    debug: bool = False
    environment: str = "development"
    
    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = False
    
    # Security
    secret_key: str = "your-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # Database
    database_url: str = "postgresql+asyncpg://user:password@localhost/farmer_ai"
    redis_url: str = "redis://localhost:6379"
    
    # Audio Processing
    whisper_model: str = "base"  # tiny, base, small, medium, large
    audio_upload_path: str = "./uploads/audio"
    max_audio_size_mb: int = 50
    supported_audio_formats: List[str] = ["wav", "mp3", "m4a", "ogg", "flac"]
    
    # NLP Models
    spacy_model: str = "en_core_web_sm"
    hindi_model: str = "hi_core_news_sm"
    sentence_transformer_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    
    # Vector Database
    vector_db_type: str = "chroma"  # chroma or faiss
    vector_db_path: str = "./data/vector_db"
    embedding_dimension: int = 384
    top_k_results: int = 5
    
    # Web Scraping
    scraper_delay: float = 1.0
    scraper_user_agent: str = "FarmerAI-Bot/1.0"
    max_pages_per_site: int = 100
    scraping_timeout: int = 30
    
    # Government Scheme URLs
    scheme_urls: List[str] = [
        "https://www.pmkisan.gov.in/",
        "https://pmfby.gov.in/",
        "https://agriwelfare.gov.in/",
        "https://vikaspedia.in/agriculture"
    ]
    # Ollama Configuration
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    ollama_timeout: int = 30
    # Celery
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/0"
    
    # Logging
    log_level: str = "INFO"
    log_file: str = "./logs/app.log"
    log_rotation: str = "1 day"
    log_retention: str = "30 days"
    
    # Rate Limiting
    rate_limit_per_minute: int = 100
    rate_limit_burst: int = 20
    
    # Languages supported
    supported_languages: List[str] = ["hi", "en", "gu", "pa", "bn", "te", "ta", "ml", "kn", "or"]
    default_language: str = "hi"
    
    # File paths
    data_path: str = "./app/data"
    models_path: str = "./models"
    temp_path: str = "./temp"
    
    # API Keys (set via environment variables)
    openai_api_key: Optional[str] = None
    huggingface_api_key: Optional[str] = None
    
    # External APIs
    weather_api_key: Optional[str] = None
    government_api_key: Optional[str] = None
    
    # Monitoring
    enable_metrics: bool = True
    metrics_port: int = 9090
    
    # CORS
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:8080"]
    cors_allow_credentials: bool = True
    cors_allow_methods: List[str] = ["GET", "POST", "PUT", "DELETE"]
    cors_allow_headers: List[str] = ["*"]
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Ensure directories exist
        os.makedirs(self.audio_upload_path, exist_ok=True)
        os.makedirs(self.data_path, exist_ok=True)
        os.makedirs(self.models_path, exist_ok=True)
        os.makedirs(self.temp_path, exist_ok=True)
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)


# Global settings instance
settings = Settings()


class DevSettings(Settings):
    """Development environment settings"""
    debug: bool = True
    reload: bool = True
    log_level: str = "DEBUG"
    environment: str = "development"


class ProdSettings(Settings):
    """Production environment settings"""
    debug: bool = False
    reload: bool = False
    log_level: str = "INFO"
    environment: str = "production"
    
    # Production security
    cors_origins: List[str] = []  # Set specific origins in production
    
    # Production performance
    rate_limit_per_minute: int = 1000
    max_audio_size_mb: int = 100


def get_settings() -> Settings:
    """Get settings based on environment"""
    env = os.getenv("ENVIRONMENT", "development").lower()
    
    if env == "production":
        return ProdSettings()
    elif env == "development":
        return DevSettings()
    else:
        return Settings()