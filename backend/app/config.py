"""Application configuration management."""

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
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # AI Provider (Ollama)
    ollama_endpoint: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen3-coder:30b"

    # Logging
    log_level: str = "INFO"

    class Config:
        """Pydantic configuration."""

        env_file = ".env"
        case_sensitive = False


settings = Settings()
