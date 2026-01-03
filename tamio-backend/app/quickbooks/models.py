"""Database models for QuickBooks integration."""
from sqlalchemy import Column, String, DateTime, Text, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from app.database import Base
import secrets


def generate_id(prefix: str) -> str:
    """Generate a unique ID with a prefix."""
    return f"{prefix}_{secrets.token_hex(6)}"


class QuickBooksConnection(Base):
    """QuickBooks connection model - stores OAuth tokens and company info."""

    __tablename__ = "quickbooks_connections"

    id = Column(String, primary_key=True, default=lambda: generate_id("qb"))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)

    # QuickBooks company info (realm_id is QuickBooks' tenant identifier)
    realm_id = Column(String, nullable=True)  # QuickBooks company ID
    company_name = Column(String, nullable=True)  # Company name

    # OAuth tokens (encrypted in production)
    access_token = Column(Text, nullable=True)
    refresh_token = Column(Text, nullable=True)
    token_expires_at = Column(DateTime(timezone=True), nullable=True)
    refresh_token_expires_at = Column(DateTime(timezone=True), nullable=True)  # QB refresh tokens expire in 100 days

    # Connection status
    is_active = Column(Boolean, nullable=False, default=False)
    last_sync_at = Column(DateTime(timezone=True), nullable=True)
    sync_error = Column(Text, nullable=True)

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class QuickBooksSyncLog(Base):
    """Log of QuickBooks sync operations for debugging and audit."""

    __tablename__ = "quickbooks_sync_logs"

    id = Column(String, primary_key=True, default=lambda: generate_id("qbsync"))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Sync details
    sync_type = Column(String, nullable=False)  # "full" | "incremental" | "invoices" | "customers"
    status = Column(String, nullable=False)  # "started" | "completed" | "failed"

    # Results
    records_fetched = Column(JSONB, nullable=True)  # {"invoices": 50, "customers": 20, ...}
    records_created = Column(JSONB, nullable=True)
    records_updated = Column(JSONB, nullable=True)
    error_message = Column(Text, nullable=True)

    # Timing
    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
