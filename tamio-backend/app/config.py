"""Application configuration."""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    DATABASE_URL: str

    # Application
    APP_ENV: str = "development"
    SECRET_KEY: str
    API_V1_PREFIX: str = "/api"

    # Frontend
    FRONTEND_URL: str = "http://localhost:3000"

    # OpenAI
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"
    OPENAI_MAX_TOKENS: int = 2000

    # Xero Integration
    XERO_CLIENT_ID: str = ""
    XERO_CLIENT_SECRET: str = ""
    XERO_REDIRECT_URI: str = "http://localhost:8000/api/xero/callback"
    XERO_SCOPES: str = "offline_access openid accounting.transactions.read accounting.contacts.read accounting.settings.read accounting.reports.read"

    # CORS
    @property
    def ALLOWED_ORIGINS(self) -> List[str]:
        if self.APP_ENV == "development":
            return ["*"]  # Allow all origins in development
        return [self.FRONTEND_URL, "http://localhost:3000"]

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True
    )


settings = Settings()
