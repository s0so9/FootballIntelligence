"""Application configuration management."""

from typing import List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # Database
    database_url: str = "sqlite:///./football_intelligence.db"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8003
    api_debug: bool = True

    # CORS
    cors_origins: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:3000",
    ]

    # AI Provider (Ollama)
    ollama_endpoint: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen3-coder:30b"

    # Football Data Providers
    # Ryzellx (PRIMARY provider)
    # Use local Ryzellx for development: http://localhost:3001
    # Use public Ryzellx for production: https://football-live-api.vercel.app
    ryzellx_base_url: str = "http://localhost:3001"
    
    # FotMob (FAST/LIVE provider)
    # Correct base URL: endpoints are /api/data/matches, /api/data/matchDetails
    fotmob_base_url: str = "https://www.fotmob.com"
    
    # OpenLigaDB (INDEPENDENT FALLBACK provider)
    openligadb_base_url: str = "https://api.openligadb.de"
    
    # Provider behavior
    provider_timeout_seconds: float = 10.0
    provider_retry_count: int = 2
    use_real_providers: bool = False  # Default False for tests, set True in production/dev env  # True = Real providers (FotMob, Ryzellx, OpenLigaDB)

    # Feature Engineering
    team_form_window: int = 5  # Number of recent matches to consider for form
    min_sample_size: int = 3  # Minimum matches needed for reliable features

    # Logging
    log_level: str = "INFO"

    class Config:
        """Pydantic configuration."""

        env_file = ".env"
        case_sensitive = False


settings = Settings()
