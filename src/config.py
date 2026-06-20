import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    telegram_bot_token: str = "" # Default empty string so we can run some tests without it
    ollama_api_url: str = "http://localhost:11434/api/generate"
    ollama_model: str = "qwen2.5:3b"
    
    db_url: str = "sqlite+aiosqlite:///personality.db"
    lancedb_path: str = "./vectors_data"
    
    emotional_inertia_alpha: float = 0.1
    base_mood: float = 0.5
    
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

settings = Settings()
