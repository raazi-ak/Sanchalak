#schemabot\app\config.py


"""
Configuration management for Sanchalak backend.

This module handles all configuration settings including database connections,
Redis caching, LLM settings, and environment-specific configurations for
the government scheme eligibility bot.
"""

import os
import secrets
from functools import lru_cache
from typing import Optional, List, Dict, Any
from pathlib import Path

from pydantic import BaseSettings, Field, validator
import structlog

logger = structlog.get_logger(__name__)


class DatabaseConfig(BaseSettings):
    """Database configuration settings."""

    url: str = Field(
        default="sqlite:///./sanchalak.db",
        env="DATABASE_URL"
    )
    pool_size: int = Field(default=10, env="DB_POOL_SIZE")
    max_overflow: int = Field(default=20, env="DB_MAX_OVERFLOW")
    pool_timeout: int = Field(default=30, env="DB_POOL_TIMEOUT")
    pool_recycle: int = Field(default=3600, env="DB_POOL_RECYCLE")
    echo: bool = Field(default=False, env="DB_ECHO")


class RedisConfig(BaseSettings):
    """Redis configuration for caching and session management."""

    url: str = Field(
        default="redis://localhost:6379/0",
        env="REDIS_URL"
    )
    password: Optional[str] = Field(default=None, env="REDIS_PASSWORD")
    max_connections: int = Field(default=20, env="REDIS_MAX_CONNECTIONS")
    socket_timeout: int = Field(default=5, env="REDIS_SOCKET_TIMEOUT")
    socket_connect_timeout: int = Field(default=5, env="REDIS_CONNECT_TIMEOUT")
    retry_on_timeout: bool = Field(default=True, env="REDIS_RETRY_ON_TIMEOUT")

    # Cache TTL settings
    default_ttl: int = Field(default=3600, env="REDIS_DEFAULT_TTL")  # 1 hour
    scheme_cache_ttl: int = Field(default=86400, env="REDIS_SCHEME_TTL")  # 24 hours
    conversation_ttl: int = Field(default=86400, env="REDIS_CONVERSATION_TTL")  # 24 hours
    eligibility_cache_ttl: int = Field(default=7200, env="REDIS_ELIGIBILITY_TTL")  # 2 hours


class LLMConfig(BaseSettings):
    """Large Language Model configuration."""

    # Gemma model settings
    model_name: str = Field(default="gemma-2b-it", env="LLM_MODEL_NAME")
    model_path: Optional[str] = Field(default=None, env="LLM_MODEL_PATH")
    device: str = Field(default="auto", env="LLM_DEVICE")  # auto, cpu, cuda
    max_tokens: int = Field(default=512, env="LLM_MAX_TOKENS")
    temperature: float = Field(default=0.7, env="LLM_TEMPERATURE")
    top_p: float = Field(default=0.9, env="LLM_TOP_P")
    top_k: int = Field(default=50, env="LLM_TOP_K")

    # Performance settings
    batch_size: int = Field(default=1, env="LLM_BATCH_SIZE")
    max_concurrent_requests: int = Field(default=5, env="LLM_MAX_CONCURRENT")
    request_timeout: int = Field(default=30, env="LLM_REQUEST_TIMEOUT")

    # Response validation
    enable_validation: bool = Field(default=True, env="LLM_ENABLE_VALIDATION")
    max_retries: int = Field(default=3, env="LLM_MAX_RETRIES")

    @validator('temperature')
    def validate_temperature(cls, v):
        if not 0.0 <= v <= 2.0:
            raise ValueError('Temperature must be between 0.0 and 2.0')
        return v

    @validator('top_p')
    def validate_top_p(cls, v):
        if not 0.0 <= v <= 1.0:
            raise ValueError('Top-p must be between 0.0 and 1.0')
        return v


class SecurityConfig(BaseSettings):
    """Security and authentication configuration."""

    secret_key: str = Field(
        default_factory=lambda: secrets.token_urlsafe(32),
        env="SECRET_KEY"
    )
    algorithm: str = Field(default="HS256", env="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=30, env="ACCESS_TOKEN_EXPIRE_MINUTES")

    # CORS settings
    allowed_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8000"],
        env="ALLOWED_ORIGINS"
    )
    allowed_methods: List[str] = Field(
        default=["GET", "POST", "PUT", "DELETE"],
        env="ALLOWED_METHODS"
    )
    allowed_headers: List[str] = Field(
        default=["*"],
        env="ALLOWED_HEADERS"
    )

    # Rate limiting
    enable_rate_limiting: bool = Field(default=True, env="ENABLE_RATE_LIMITING")
    rate_limit_requests: int = Field(default=100, env="RATE_LIMIT_REQUESTS")
    rate_limit_period: int = Field(default=60, env="RATE_LIMIT_PERIOD")  # seconds


class MonitoringConfig(BaseSettings):
    """Monitoring and observability configuration."""

    # Logging
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_format: str = Field(default="json", env="LOG_FORMAT")  # json, text
    enable_request_logging: bool = Field(default=True, env="ENABLE_REQUEST_LOGGING")

    # Metrics
    enable_metrics: bool = Field(default=True, env="ENABLE_METRICS")
    metrics_port: int = Field(default=8001, env="METRICS_PORT")
    metrics_path: str = Field(default="/metrics", env="METRICS_PATH")

    # Health checks
    health_check_timeout: int = Field(default=5, env="HEALTH_CHECK_TIMEOUT")

    @validator('log_level')
    def validate_log_level(cls, v):
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in valid_levels:
            raise ValueError(f'Log level must be one of: {valid_levels}')
        return v.upper()


class SchemeConfig(BaseSettings):
    """Scheme processing configuration."""

    # File paths
    schemes_directory: str = Field(default="schemas", env="SCHEMES_DIRECTORY")
    registry_file: str = Field(default="schemas/schemes_registry.yaml", env="REGISTRY_FILE")

    # Processing settings
    enable_scheme_caching: bool = Field(default=True, env="ENABLE_SCHEME_CACHING")
    scheme_validation_strict: bool = Field(default=True, env="SCHEME_VALIDATION_STRICT")
    auto_reload_schemes: bool = Field(default=False, env="AUTO_RELOAD_SCHEMES")

    # Supported languages
    supported_languages: List[str] = Field(
        default=["hi", "en", "bn", "te", "ta", "gu", "mr", "kn", "ml", "or", "pa", "as"],
        env="SUPPORTED_LANGUAGES"
    )
    default_language: str = Field(default="hi", env="DEFAULT_LANGUAGE")

    @validator('schemes_directory')
    def validate_schemes_directory(cls, v):
        path = Path(v)
        if not path.exists():
            logger.warning(f"Schemes directory does not exist: {v}")
        return v


class ConversationConfig(BaseSettings):
    """Conversation management configuration."""

    # Session settings
    session_timeout: int = Field(default=1800, env="SESSION_TIMEOUT")  # 30 minutes
    max_messages_per_conversation: int = Field(default=50, env="MAX_MESSAGES_PER_CONVERSATION")
    max_data_collection_attempts: int = Field(default=3, env="MAX_DATA_COLLECTION_ATTEMPTS")

    # Response settings
    enable_typing_indicators: bool = Field(default=True, env="ENABLE_TYPING_INDICATORS")
    response_delay_ms: int = Field(default=500, env="RESPONSE_DELAY_MS")

    # Data validation
    enable_input_sanitization: bool = Field(default=True, env="ENABLE_INPUT_SANITIZATION")
    max_input_length: int = Field(default=1000, env="MAX_INPUT_LENGTH")


class Settings(BaseSettings):
    """Main application settings."""

    # Application metadata
    app_name: str = Field(default="Sanchalak", env="APP_NAME")
    app_version: str = Field(default="1.0.0", env="APP_VERSION")
    app_description: str = Field(
        default="Government Scheme Eligibility Bot for Farmers",
        env="APP_DESCRIPTION"
    )

    # Environment
    environment: str = Field(default="development", env="ENVIRONMENT")
    debug: bool = Field(default=False, env="DEBUG")

    # Server settings
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8000, env="PORT")
    workers: int = Field(default=1, env="WORKERS")

    # Sub-configurations
    database: DatabaseConfig = DatabaseConfig()
    redis: RedisConfig = RedisConfig()
    llm: LLMConfig = LLMConfig()
    security: SecurityConfig = SecurityConfig()
    monitoring: MonitoringConfig = MonitoringConfig()
    schemes: SchemeConfig = SchemeConfig()
    conversations: ConversationConfig = ConversationConfig()

    @validator('environment')
    def validate_environment(cls, v):
        valid_envs = ['development', 'staging', 'production']
        if v not in valid_envs:
            raise ValueError(f'Environment must be one of: {valid_envs}')
        return v

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == "development"

    def get_database_url(self) -> str:
        """Get formatted database URL."""
        return self.database.url

    def get_redis_url(self) -> str:
        """Get formatted Redis URL."""
        return self.redis.url

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached application settings.

    Returns:
        Settings: Application configuration object
    """
    settings = Settings()

    # Log configuration on startup
    logger.info(
        "Application configuration loaded",
        app_name=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
        debug=settings.debug
    )

    return settings


# Global settings instance
settings = get_settings()


# Environment-specific settings
def get_env_settings() -> Dict[str, Any]:
    """Get environment-specific configuration overrides."""
    env_configs = {
        "development": {
            "database": {"echo": True},
            "monitoring": {"log_level": "DEBUG"},
            "llm": {"max_concurrent_requests": 2},
            "security": {"enable_rate_limiting": False}
        },
        "staging": {
            "database": {"echo": False},
            "monitoring": {"log_level": "INFO"},
            "llm": {"max_concurrent_requests": 3},
            "security": {"enable_rate_limiting": True}
        },
        "production": {
            "database": {"echo": False},
            "monitoring": {"log_level": "WARNING"},
            "llm": {"max_concurrent_requests": 5},
            "security": {"enable_rate_limiting": True}
        }
    }

    return env_configs.get(settings.environment, {})


def validate_configuration() -> bool:
    """
    Validate all configuration settings.

    Returns:
        bool: True if configuration is valid
    """
    try:
        # Check required directories
        schemes_path = Path(settings.schemes.schemes_directory)
        if not schemes_path.exists():
            logger.warning(f"Schemes directory does not exist: {schemes_path}")

        # Validate Redis connection format
        if not settings.redis.url.startswith(('redis://', 'rediss://')):
            logger.error("Invalid Redis URL format")
            return False

        # Check LLM configuration
        if settings.llm.temperature < 0 or settings.llm.temperature > 2:
            logger.error("Invalid LLM temperature setting")
            return False

        logger.info("Configuration validation passed")
        return True

    except Exception as e:
        logger.error(f"Configuration validation failed: {e}")
        return False


if __name__ == "__main__":
    # Test configuration loading
    config = get_settings()
    print(f"Loaded configuration for {config.app_name} v{config.app_version}")
    print(f"Environment: {config.environment}")
    print(f"Database: {config.get_database_url()}")
    print(f"Redis: {config.get_redis_url()}")

    # Validate configuration
    is_valid = validate_configuration()
    print(f"Configuration valid: {is_valid}")
