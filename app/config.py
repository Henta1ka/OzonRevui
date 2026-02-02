"""Application configuration"""
from pydantic_settings import BaseSettings
import os


class Settings(BaseSettings):
    """Application settings"""
    
    # Database
    database_url: str = "sqlite:///./ozon_reviews.db"
    
    # Ozon API
    ozon_client_id: str = ""
    ozon_api_key: str = ""
    
    # OpenAI API
    openai_api_key: str = ""
    openai_model: str = "gpt-3.5-turbo"  # gpt-3.5-turbo, gpt-4, gpt-4-turbo
    
    # YandexGPT API
    yandex_api_key: str = ""
    yandex_folder_id: str = ""
    yandex_model: str = "yandexgpt-3"  # yandexgpt-3, yandexgpt-3-pro
    
    # AI Provider selection
    ai_provider: str = "openai"  # openai or yandex
    
    # Response settings
    response_tone: str = "friendly"  # friendly, official, formal
    response_signature: str = "С уважением,\nКоманда маркетплейса"
    response_prompt: str = ""  # Custom prompt template for auto responses
    
    # AI settings
    ai_enabled: bool = True  # Disable if quota exceeded
    ai_timeout: int = 10  # Seconds before giving up on API call

    # Auto-response settings
    auto_response_enabled: bool = False  # Auto-generate draft on new reviews
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
    # Server settings
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000
    
    # Polling settings
    polling_interval_minutes: int = 30  # How often to fetch new reviews
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
