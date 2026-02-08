"""Database models for Xero integration."""
from sqlalchemy import Column, String, DateTime, Text, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.database import Base
from app.models.base import generate_id


class XeroConnection(Base):
    """Xero connection model - stores OAuth tokens and tenant info."""

    __tablename__ = "xero_connections"

    id = Column(String, primary_key=True, default=lambda: generate_id("xero"))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)

    # Xero tenant info
    tenant_id = Column(String, nullable=True)  # Xero organization ID
    tenant_name = Column(String, nullable=True)  # Organization name

    # OAuth tokens (encrypted in production)
    access_token = Column(Text, nullable=True)
    refresh_token = Column(Text, nullable=True)
    token_expires_at = Column(DateTime(timezone=True), nullable=True)

    # Token metadata
    scopes = Column(Text, nullable=True)  # Space-separated scopes
    id_token = Column(Text, nullable=True)  # OpenID Connect token

    # Connection status
    is_active = Column(Boolean, nullable=False, default=False)
    last_sync_at = Column(DateTime(timezone=True), nullable=True)
    sync_error = Column(Text, nullable=True)

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class OAuthState(Base):
    """OAuth state storage - persists state tokens for OAuth flow.

    Replaces in-memory state storage to survive server restarts.
    """

    __tablename__ = "oauth_states"

    id = Column(String, primary_key=True, default=lambda: generate_id("oauth"))
    state = Column(String, nullable=False, unique=True, index=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    provider = Column(String, nullable=False, default="xero")  # "xero" | "quickbooks"

    # Expiry - states should only be valid for a short time
    expires_at = Column(DateTime(timezone=True), nullable=False)

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class XeroSyncLog(Base):
    """Log of Xero sync operations for debugging and audit."""

    __tablename__ = "xero_sync_logs"

    id = Column(String, primary_key=True, default=lambda: generate_id("sync"))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Sync details
    sync_type = Column(String, nullable=False)  # "full" | "incremental" | "invoices" | "contacts"
    status = Column(String, nullable=False)  # "started" | "completed" | "failed"

    # Results
    records_fetched = Column(JSONB, nullable=True)  # {"invoices": 50, "contacts": 20, ...}
    records_created = Column(JSONB, nullable=True)
    records_updated = Column(JSONB, nullable=True)
    error_message = Column(Text, nullable=True)

    # Timing
    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
