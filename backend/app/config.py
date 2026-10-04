"""Application configuration management."""

from typing import List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # Database
    database_url: str = "sqlite:///./football_intelligence.db"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_debug: bool = True

    # CORS
    cors_origins: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    # AI Provider (Ollama)
    ollama_endpoint: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen3-coder:30b"

    # Football Data Providers
    # Ryzellx (PRIMARY provider)
    ryzellx_base_url: str = "https://football-live-api.vercel.app"
    
    # FotMob (FAST/LIVE provider)
    fotmob_base_url: str = "https://www.fotmob.com/api"
    
    # OpenLigaDB (INDEPENDENT FALLBACK provider)
    openligadb_base_url: str = "https://api.openligadb.de"
    
    # Provider behavior
    provider_timeout_seconds: float = 10.0
    provider_retry_count: int = 2
    use_real_providers: bool = False  # False = DevelopmentProvider (default)

    # Logging
    log_level: str = "INFO"

    class Config:
        """Pydantic configuration."""

        env_file = ".env"
        case_sensitive = False


settings = Settings()
