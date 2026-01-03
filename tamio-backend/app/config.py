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

    # Frontend (Vite dev server runs on 5173 by default)
    FRONTEND_URL: str = "http://localhost:5173"

    # OpenAI
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"
    OPENAI_MODEL_FAST: str = "gpt-4o-mini"  # Faster model for simple queries
    OPENAI_MAX_TOKENS: int = 2000

    # Xero Integration
    XERO_CLIENT_ID: str = ""
    XERO_CLIENT_SECRET: str = ""
    XERO_REDIRECT_URI: str = "http://localhost:8000/api/xero/callback"
    # Xero scopes - includes both read and write for bi-directional sync
    # Read: pull transactions, contacts, settings, reports from Xero
    # Write: push contacts and transactions (invoices, bills) to Xero
    XERO_SCOPES: str = "offline_access openid accounting.transactions accounting.contacts accounting.settings.read accounting.reports.read"

    # QuickBooks Integration
    QUICKBOOKS_CLIENT_ID: str = ""
    QUICKBOOKS_CLIENT_SECRET: str = ""
    QUICKBOOKS_REDIRECT_URI: str = "http://localhost:8000/api/quickbooks/callback"
    QUICKBOOKS_ENVIRONMENT: str = "sandbox"  # "sandbox" or "production"
    # QuickBooks scope for accounting access
    QUICKBOOKS_SCOPES: str = "com.intuit.quickbooks.accounting"

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
