#schemabot\app\config.py


"""
Configuration management for Sanchalak using Pydantic V2.
"""

"""
Configuration management for Sanchalak using Pydantic V2.
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator, ConfigDict
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseConfig(BaseModel):
    """Database configuration settings."""
    url: str = Field(default="sqlite:///./sanchalak.db")
    echo: bool = Field(default=False)
    pool_size: int = Field(default=5, ge=1, le=20)
    max_overflow: int = Field(default=10, ge=0, le=50)


class RedisConfig(BaseModel):
    """Redis configuration settings."""
    url: str = Field(default="redis://localhost:6379/0")
    default_ttl: int = Field(default=3600, ge=60, le=86400)
    max_connections: int = Field(default=10, ge=1, le=100)


class LLMConfig(BaseModel):
    model_config = ConfigDict(protected_namespaces=())


    """LLM configuration settings."""
    model_name: str = Field(default="gemma-2b-it")
    max_tokens: int = Field(default=512, ge=50, le=4096)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_concurrent_requests: int = Field(default=5, ge=1, le=20)
    timeout: int = Field(default=30, ge=5, le=300)


class SchemeConfig(BaseModel):
    """Scheme processing configuration."""
    directory: Path = Field(default=Path("schemas"))
    registry_file: Path = Field(default=Path("schemas/schemes_registry.yaml"))
    supported_languages: List[str] = Field(default=["hi", "en", "bn", "te", "ta"])
    default_language: str = Field(default="hi")
    cache_ttl: int = Field(default=1800, ge=300, le=7200)


class SecurityConfig(BaseModel):
    """Security configuration settings."""
    secret_key: str = Field(default="dev-secret-key-change-in-production")
    enable_cors: bool = Field(default=True)
    cors_origins: List[str] = Field(default=["*"])
    enable_rate_limiting: bool = Field(default=True)
    rate_limit_per_minute: int = Field(default=60, ge=10, le=1000)


class MonitoringConfig(BaseModel):
    """Monitoring and observability configuration."""
    enable_metrics: bool = Field(default=True)
    enable_request_logging: bool = Field(default=True)
    log_level: str = Field(default="INFO")
    metrics_port: int = Field(default=9090, ge=1024, le=65535)


class ConversationConfig(BaseModel):
    """Conversation management configuration."""
    session_timeout: int = Field(default=1800, ge=300, le=7200)
    max_messages_per_conversation: int = Field(default=50, ge=5, le=200)
    auto_cleanup_interval: int = Field(default=3600, ge=300, le=86400)


class Settings(BaseSettings):
    """Main application settings."""
    
    model_config = SettingsConfigDict(
        env_prefix="SANCHALAK_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Application metadata
    app_name: str = Field(default="Sanchalak")
    app_version: str = Field(default="1.0.0")
    environment: str = Field(default="development")
    debug: bool = Field(default=False)
    
    # Configuration sections
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    schemes: SchemeConfig = Field(default_factory=SchemeConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)
    conversation: ConversationConfig = Field(default_factory=ConversationConfig)
    
    # Direct environment overrides
    database_url: Optional[str] = Field(default=None)
    redis_url: Optional[str] = Field(default=None)
    log_level: Optional[str] = Field(default=None)
    
    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        allowed = ["development", "staging", "production", "test"]
        if v.lower() not in allowed:
            raise ValueError(f"Environment must be one of: {allowed}")
        return v.lower()
    
    def get_database_url(self) -> str:
        """Get the database URL, preferring direct override."""
        return self.database_url or self.database.url
    
    def get_redis_url(self) -> str:
        """Get the Redis URL, preferring direct override."""
        return self.redis_url or self.redis.url
    
    def get_log_level(self) -> str:
        """Get the log level, preferring direct override."""
        return (self.log_level or self.monitoring.log_level).upper()
    
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == "production"
    
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == "development"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


def validate_configuration() -> bool:
    """Validate the current configuration."""
    try:
        settings = get_settings()
        
        # Validate database URL format
        db_url = settings.get_database_url()
        if not db_url.startswith(("sqlite://", "postgresql://", "mysql://")):
            raise ValueError(f"Invalid database URL format: {db_url}")
        
        # Validate Redis URL format
        redis_url = settings.get_redis_url()
        if not redis_url.startswith("redis://"):
            raise ValueError(f"Invalid Redis URL format: {redis_url}")
        
        return True
        
    except Exception as e:
        print(f"Configuration validation failed: {e}")
        return False
