import os
from pydantic_settings import BaseSettings
from typing import List, Optional

class Settings(BaseSettings):
    """Configuration settings for Telegram Bot"""
    
    # Telegram Bot
    telegram_bot_token: str
    bot_username: Optional[str] = "sanchalak_bot"
    
    # MongoDB
    mongo_uri: str = "mongodb://localhost:27017"  # Local MongoDB for testing
    mongo_db_name: str = "sanchalak"
    
    # OpenRouter API (better than direct OpenAI)
    openrouter_api_key: Optional[str] = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    default_model: str = "openai/gpt-3.5-turbo"  # Can switch to any model
    
    # Available models for different purposes
    quick_response_model: str = "openai/gpt-3.5-turbo"  # Fast responses
    detailed_model: str = "openai/gpt-4"  # Better quality
    
    # File Storage
    upload_dir: str = "./uploads"  # Local directory for testing
    max_file_size_mb: int = 50
    
    # Session Management
    session_timeout_minutes: int = 120  # 2 hours for farmers to explain properly
    max_messages_per_session: int = 50
    
    # Orchestrator Integration (for later)
    orchestrator_url: str = "http://orchestrator:8000"  # Docker service name for production
    orchestrator_timeout: int = 30
    
    # Logging
    log_level: str = "INFO"
    log_file: str = "./logs/bot.log"  # Local directory for testing
    
    # Development/Testing
    debug_mode: bool = False
    mock_responses: bool = False  # Use real orchestrator by default
    
    # Multilingual Support
    supported_languages: list[str] = [
        "hindi", "english", "bengali", "telugu", "marathi", 
        "tamil", "gujarati", "punjabi", "kannada", "malayalam",
        "odia", "assamese", "urdu", "rajasthani", "bhojpuri"
    ]
    default_language: str = "hi"
    
    class Config:
        env_file = [".env.local", ".env"]  # Try .env.local first, then .env
        env_file_encoding = "utf-8"
        case_sensitive = False

# Global settings instance
settings = Settings()

# Create required directories
os.makedirs(settings.upload_dir, exist_ok=True)
os.makedirs(os.path.dirname(settings.log_file), exist_ok=True) 