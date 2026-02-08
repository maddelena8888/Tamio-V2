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

    # Anthropic (Claude)
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-4-20250514"
    ANTHROPIC_MODEL_FAST: str = "claude-sonnet-4-20250514"  # Use same model (Haiku may not be available on all API keys)
    ANTHROPIC_MAX_TOKENS: int = 2000

    # Xero Integration
    XERO_CLIENT_ID: str = ""
    XERO_CLIENT_SECRET: str = ""
    XERO_REDIRECT_URI: str = "http://localhost:8000/api/xero/callback"
    # Xero scopes - includes both read and write for bi-directional sync
    # Read: pull transactions, contacts, settings, reports from Xero
    # Write: push contacts and transactions (invoices, bills) to Xero
    XERO_SCOPES: str = "offline_access openid accounting.transactions accounting.contacts accounting.settings.read accounting.reports.read"

    # Demo Account
    DEMO_TOKEN: str = "DEMO_TOKEN_2026"
    DEMO_ACCOUNT_EMAIL: str = "demo@agencyco.com"

    # ==========================================================================
    # Email Notifications (Resend)
    # ==========================================================================
    # Get your API key at https://resend.com
    RESEND_API_KEY: str = ""
    NOTIFICATION_FROM_EMAIL: str = "Tamio <notifications@tamio.app>"

    # ==========================================================================
    # Slack Notifications
    # ==========================================================================
    # Create a Slack app at https://api.slack.com/apps and get a Bot Token
    SLACK_BOT_TOKEN: str = ""
    SLACK_DEFAULT_CHANNEL: str = "#treasury-alerts"

    # ==========================================================================
    # Rate Limiting
    # ==========================================================================
    RATE_LIMIT_DEFAULT: str = "100/minute"  # General API endpoints
    RATE_LIMIT_TAMI: str = "20/minute"       # Claude/TAMI calls (expensive)
    RATE_LIMIT_XERO: str = "30/minute"       # Xero API calls

    # Sentry (error tracking)
    SENTRY_DSN: str = ""

    # CORS
    @property
    def ALLOWED_ORIGINS(self) -> List[str]:
        if self.APP_ENV == "development":
            return ["*"]  # Allow all origins in development
        return [self.FRONTEND_URL, "http://localhost:3000"]

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore"  # Allow extra env vars not defined in Settings
    )


settings = Settings()
