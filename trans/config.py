from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Whisper Model
    WHISPER_MODEL: str
    SUPPORTED_AUDIO_FORMATS: str

    # Azure Translation
    AZURE_TRANSLATOR_KEY: str
    AZURE_TRANSLATOR_REGION: str
    AZURE_TRANSLATOR_ENDPOINT: str

    # Azure TTS
    AZURE_TTS_KEY: str
    AZURE_TTS_REGION: str
    AZURE_TTS_ENDPOINT: str

    # Logging
    LOG_LEVEL: str = "debug"

    BACKEND_URL: str = "http://127.0.0.1:8000"


    class Config:
        env_file = ".env"


@lru_cache()
def get_settings():
    return Settings()
